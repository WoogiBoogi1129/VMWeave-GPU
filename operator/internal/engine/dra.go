package engine

import (
	"fmt"
	"strconv"

	"k8s.io/apimachinery/pkg/api/resource"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
)

const hamiDRADriver = "hami-core-gpu.project-hami.io"

func backend(p *Obj) string {
	if b := S(p, "spec", "backend"); b != "" {
		return b
	}
	return "hami"
}

func validateBackend(p *Obj) error {
	switch backend(p) {
	case "hami":
		return nil
	case "hami-dra":
		if S(p, "spec", "draDeviceClass") == "" || S(p, "spec", "schedulerName") == "hami-scheduler" {
			return invalid("DRA requires a DeviceClass and a DRA-capable scheduler")
		}
		return nil
	default:
		return invalid("unsupported GPU backend")
	}
}

func (a API) checkDRAProfile(p *Obj) error {
	if backend(p) != "hami-dra" {
		return nil
	}
	class, err := a.Get("deviceclasses", S(p, "spec", "draDeviceClass"))
	if err != nil {
		return err
	}
	if class == nil {
		return WaitError{"DRADeviceClassUnavailable"}
	}
	list := &unstructured.UnstructuredList{}
	list.SetAPIVersion("resource.k8s.io/v1")
	list.SetKind("ResourceSliceList")
	if err := a.R.List(a.Context, list); err != nil {
		return err
	}
	for _, slice := range list.Items {
		if S(&slice, "spec", "driver") != hamiDRADriver || S(&slice, "spec", "nodeName") != S(p, "spec", "nodeName") {
			continue
		}
		devices, _, _ := unstructured.NestedSlice(slice.Object, "spec", "devices")
		for _, d := range devices {
			dev := &Obj{Object: d.(map[string]interface{})}
			if S(dev, "attributes", "uuid", "string") == S(p, "spec", "gpuUUID") {
				return nil
			}
		}
	}
	return WaitError{"DRAGPUNotPublished"}
}

// Claims are tied to an allocation generation, not merely the reusable channel.
func draClaim(c, p *Obj) *Obj {
	mem := resource.MustParse(fmt.Sprintf("%dMi", N(c, "status", "memoryMiB")))
	o := Child("claims", ResourceName(c, "gpu"), c)
	o.SetAnnotations(map[string]string{Group + "/allocation": S(c, "status", "allocation")})
	expr := fmt.Sprintf("device.driver == %s && device.attributes[%s].uuid == %s",
		strconv.Quote(hamiDRADriver), strconv.Quote(hamiDRADriver), strconv.Quote(S(c, "status", "gpuUUID")))
	Set(o, Map{"devices": Map{"requests": []interface{}{Map{
		"name": "gpu", "exactly": Map{
			"deviceClassName": S(p, "spec", "draDeviceClass"),
			"allocationMode":  "ExactCount", "count": int64(1),
			"selectors": []interface{}{Map{"cel": Map{"expression": expr}}},
			"capacity":  Map{"requests": Map{"memory": mem.String(), "cores": fmt.Sprint(N(c, "status", "compute"))}},
		},
	}}}}, "spec")
	return o
}

func (a API) ensureDRAClaim(c, p *Obj) (*Obj, error) {
	want := draClaim(c, p)
	if uid := S(c, "status", "claimUID"); uid != "" {
		existing, err := a.Get("claims", want.GetName())
		if err != nil {
			return nil, err
		}
		if existing == nil || string(existing.GetUID()) != uid {
			return nil, invalid("DRA claim identity unavailable; refusing replacement")
		}
	}
	o, err := a.Ensure(want, c)
	if err != nil {
		return nil, err
	}
	if o.GetDeletionTimestamp() != nil || o.GetAnnotations()[Group+"/allocation"] != S(c, "status", "allocation") || !Equal(Get(o, "spec"), Get(want, "spec")) {
		return nil, invalid("DRA claim generation or specification changed")
	}
	if uid := S(c, "status", "claimUID"); uid != "" && uid != string(o.GetUID()) {
		return nil, invalid("DRA claim identity changed")
	}
	if S(c, "status", "claimUID") == "" {
		if err := a.Status(c, Map{"claimName": o.GetName(), "claimUID": string(o.GetUID())}); err != nil {
			return nil, err
		}
	}
	return o, nil
}

// Check the allocated device against the published inventory before reporting Ready.
func (a API) checkDRA(c *Obj, w *Obj) error {
	if S(c, "status", "backend") != "hami-dra" {
		return nil
	}
	claim, err := a.Get("claims", S(c, "status", "claimName"))
	if err != nil {
		return err
	}
	if claim == nil || !Owned(claim, c) || string(claim.GetUID()) != S(c, "status", "claimUID") || claim.GetDeletionTimestamp() != nil {
		return invalid("DRA claim identity unavailable")
	}
	results, _, _ := unstructured.NestedSlice(claim.Object, "status", "allocation", "devices", "results")
	if len(results) == 0 {
		return WaitError{"DRAAllocationPending"}
	}
	if len(results) != 1 {
		return invalid("DRA must allocate exactly one GPU")
	}
	r := &Obj{Object: results[0].(map[string]interface{})}
	if S(r, "driver") != hamiDRADriver || S(r, "request") != "gpu" {
		return invalid("unexpected DRA allocation")
	}
	for key, expected := range map[string]string{"memory": fmt.Sprintf("%dMi", N(c, "status", "memoryMiB")), "cores": fmt.Sprint(N(c, "status", "compute"))} {
		actual, err := resource.ParseQuantity(S(r, "consumedCapacity", key))
		want := resource.MustParse(expected)
		if err != nil || actual.Cmp(want) != 0 {
			return invalid("DRA allocated capacity mismatch")
		}
	}
	if S(w, "spec", "nodeName") == "" {
		return WaitError{"DRAWorkerScheduling"}
	}
	if S(w, "spec", "nodeName") != S(c, "status", "nodeName") {
		return invalid("DRA worker node mismatch")
	}
	list := &unstructured.UnstructuredList{}
	list.SetAPIVersion("resource.k8s.io/v1")
	list.SetKind("ResourceSliceList")
	if err := a.R.List(a.Context, list); err != nil {
		return err
	}
	for _, slice := range list.Items {
		if S(&slice, "spec", "driver") != hamiDRADriver || S(&slice, "spec", "pool", "name") != S(r, "pool") || S(&slice, "spec", "nodeName") != S(c, "status", "nodeName") {
			continue
		}
		devices, _, _ := unstructured.NestedSlice(slice.Object, "spec", "devices")
		for _, d := range devices {
			dev := &Obj{Object: d.(map[string]interface{})}
			if S(dev, "name") == S(r, "device") && S(dev, "attributes", "uuid", "string") == S(c, "status", "gpuUUID") {
				return nil
			}
		}
	}
	return WaitError{"DRAAllocatedDeviceNotInInventory"}
}

func (a API) releaseDRA(c *Obj) error {
	if S(c, "status", "backend") != "hami-dra" {
		return nil
	}
	// A claim can exist even if recording its UID failed.
	o, err := a.Get("claims", ResourceName(c, "gpu"))
	if err != nil || o == nil {
		return err
	}
	if !Owned(o, c) || o.GetAnnotations()[Group+"/allocation"] != S(c, "status", "allocation") {
		return invalid("refusing to release foreign DRA claim")
	}
	if uid := S(c, "status", "claimUID"); uid != "" && uid != string(o.GetUID()) {
		return invalid("refusing to release replaced DRA claim")
	}
	w, err := a.Get("pods", ResourceName(c, "worker"))
	if err != nil {
		return err
	}
	if w != nil {
		return WaitError{"AwaitingDRAWorkerDeletion"}
	}
	if o.GetDeletionTimestamp() == nil {
		if err := a.Delete(o); err != nil {
			return err
		}
	}
	return WaitError{"DRAClaimReleasePending"}
}
