package engine

import (
	"testing"

	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/types"
)

func draFixture() (*Obj, *Obj) {
	c := channel("a")
	Set(c, Map{"backend": "hami-dra", "allocation": "a1", "generation": "g1", "gpuUUID": "GPU-test", "nodeName": "node1", "memoryMiB": int64(8192), "compute": int64(50)}, "status")
	p := obj("profiles", "a", "profile", "profile1")
	Set(p, Map{"backend": "hami-dra", "draDeviceClass": hamiDRADriver, "schedulerName": "default-scheduler"}, "spec")
	return c, p
}

func TestDRAClaimIdentityAndCapacity(t *testing.T) {
	c, p := draFixture()
	o := draClaim(c, p)
	o.SetUID(types.UID("claim1"))
	a := fakeAPI("a", c, o)
	got, err := a.ensureDRAClaim(c, p)
	if err != nil || got.GetUID() != o.GetUID() || S(c, "status", "claimUID") != "claim1" {
		t.Fatal(got, err)
	}
	Set(c, int64(4096), "status", "memoryMiB")
	if _, err = a.ensureDRAClaim(c, p); err == nil {
		t.Fatal("changed capacity accepted")
	}
	Set(c, int64(8192), "status", "memoryMiB")
	Set(c, "another", "status", "claimUID")
	if _, err = a.ensureDRAClaim(c, p); err == nil {
		t.Fatal("replacement claim accepted")
	}
}

func TestDRAReleaseWaitsForWorker(t *testing.T) {
	c, p := draFixture()
	o := draClaim(c, p)
	w := Child("pods", ResourceName(c, "worker"), c)
	a := fakeAPI("a", c, o, w)
	if err := a.releaseDRA(c); err == nil {
		t.Fatal("release reported complete while worker exists")
	}
	if claim, _ := a.Get("claims", o.GetName()); claim == nil {
		t.Fatal("claim deleted before worker")
	}
	if err := a.Delete(w); err != nil {
		t.Fatal(err)
	}
	_ = a.releaseDRA(c)
	if err := a.releaseDRA(c); err != nil {
		t.Fatal(err)
	}
}

func TestDRAWorkerDoesNotRequestExtendedResources(t *testing.T) {
	c, p := draFixture()
	o := draClaim(c, p)
	o.SetUID(types.UID("claim1"))
	a := fakeAPI("a", c, o, Child("roles", ResourceName(c, "worker"), c), Child("rolebindings", ResourceName(c, "worker"), c))
	w, err := a.Worker(c, p, Options{})
	if err != nil {
		t.Fatal(err)
	}
	containers := Get(w, "spec", "containers").([]interface{})
	res := containers[0].(map[string]interface{})["resources"].(map[string]interface{})
	if res["limits"] != nil || res["requests"] != nil || res["claims"] == nil {
		t.Fatal(res)
	}
	if w.GetAnnotations()["nvidia.com/use-gpuuuid"] != "" || S(w, "spec", "schedulerName") != "default-scheduler" {
		t.Fatal(w)
	}
	if err := a.checkDRA(c, w); err == nil {
		t.Fatal("unallocated claim accepted")
	}
}

func TestBackendValidation(t *testing.T) {
	_, p := draFixture()
	if err := validateBackend(p); err != nil {
		t.Fatal(err)
	}
	Set(p, "hami-scheduler", "spec", "schedulerName")
	if validateBackend(p) == nil {
		t.Fatal("classic scheduler accepted for DRA")
	}
	if backend(New("profiles")) != "hami" {
		t.Fatal("legacy default changed")
	}
}

func TestDRAAllocatedDeviceMustMatchProfile(t *testing.T) {
	c, p := draFixture()
	claim := draClaim(c, p)
	claim.SetUID("claim1")
	Set(c, claim.GetName(), "status", "claimName")
	Set(c, "claim1", "status", "claimUID")
	result := Map{"request": "gpu", "driver": hamiDRADriver, "pool": "node1", "device": "hami-gpu-2", "consumedCapacity": Map{"memory": "8Gi", "cores": "50"}}
	Set(claim, []interface{}{result}, "status", "allocation", "devices", "results")
	w := Child("pods", ResourceName(c, "worker"), c)
	Set(w, "node1", "spec", "nodeName")
	slice := &unstructured.Unstructured{Object: Map{"apiVersion": "resource.k8s.io/v1", "kind": "ResourceSlice", "metadata": Map{"name": "slice"},
		"spec": Map{"nodeName": "node1", "driver": hamiDRADriver, "pool": Map{"name": "node1"}, "devices": []interface{}{Map{"name": "hami-gpu-2", "attributes": Map{"uuid": Map{"string": "GPU-test"}}}}}}}
	a := fakeAPI("a", c, claim, slice)
	if err := a.checkDRA(c, w); err != nil {
		t.Fatal(err)
	}
	Set(w, "wrong-node", "spec", "nodeName")
	if a.checkDRA(c, w) == nil {
		t.Fatal("wrong node accepted")
	}
	Set(w, "node1", "spec", "nodeName")
	Set(c, "GPU-other", "status", "gpuUUID")
	if a.checkDRA(c, w) == nil {
		t.Fatal("wrong GPU accepted")
	}
	Set(c, "GPU-test", "status", "gpuUUID")
	Set(c, int64(25), "status", "compute")
	if a.checkDRA(c, w) == nil {
		t.Fatal("wrong capacity accepted")
	}
}

func TestDRAReleaseDoesNotDeleteForeignClaim(t *testing.T) {
	c, p := draFixture()
	claim := draClaim(c, p)
	claim.SetOwnerReferences(nil)
	a := fakeAPI("a", c, claim)
	if a.releaseDRA(c) == nil {
		t.Fatal("foreign claim accepted")
	}
	if o, _ := a.Get("claims", claim.GetName()); o == nil {
		t.Fatal("foreign claim deleted")
	}
}

func TestDRAClaimLossDoesNotCreateReplacement(t *testing.T) {
	c, p := draFixture()
	Set(c, "lost-claim", "status", "claimUID")
	a := fakeAPI("a", c)
	if _, err := a.ensureDRAClaim(c, p); err == nil {
		t.Fatal("missing recorded claim accepted")
	}
	if o, _ := a.Get("claims", ResourceName(c, "gpu")); o != nil {
		t.Fatal("replacement claim was created")
	}
}
