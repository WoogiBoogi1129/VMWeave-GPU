package engine

import (
	"encoding/json"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// A completion record belongs to one allocation, not to the lifetime of a VM.
// Write it only after detach, successful backing reclamation and DRA release.
func completionIdentity(c *Obj) Map {
	return Map{"channelUID": string(c.GetUID()), "vmUID": S(c, "spec", "vmRef", "uid"), "pvcUID": S(c, "spec", "pvcRef", "uid"),
		"allocation": S(c, "status", "allocation"), "generation": S(c, "status", "generation"),
		"vmiUID": S(c, "status", "vmiUID"), "workerPodUID": S(c, "status", "workerPodUID"),
		"backend": S(c, "status", "backend"), "claimUID": S(c, "status", "claimUID"), "claimName": S(c, "status", "claimName")}
}

func completed(c *Obj) bool {
	if S(c, "spec", "pvcRef", "uid") == "" {
		return false
	}
	if S(c, "status", "allocation") == "" {
		if !persistent(c) {
			return false
		}
		for _, k := range []string{"generation", "vmiUID", "workerPodUID", "backend", "claimUID", "claimName"} {
			if S(c, "status", k) != "" {
				return false
			}
		}
	} else if S(c, "status", "generation") == "" {
		return false
	}
	for k, v := range completionIdentity(c) {
		if !Equal(Get(c, "status", "completion", k), v) {
			return false
		}
	}
	_, err := time.Parse(time.RFC3339Nano, S(c, "status", "completion", "completedAt"))
	return err == nil
}

func (a API) recordCompletion(c *Obj, phase string) error {
	r := completionIdentity(c)
	r["completedAt"] = time.Now().UTC().Format(time.RFC3339Nano)
	return a.Status(c, Map{"phase": phase, "reason": "DetachAndReclamationConfirmed", "completion": r})
}

// Released is terminal. Never re-enter Observe/Drain and act on a newer VM boot.
// Historical Released objects without a receipt are preserved for verification.
func (a API) finishReleased(c *Obj) error {
	if !completed(c) {
		if c.GetDeletionTimestamp() == nil {
			return nil
		}
		return WaitError{"ReleasedCompletionEvidenceRequired"}
	}
	if err := a.cleanupReclamation(c); err != nil {
		return err
	}
	if err := a.clearCompletedBinding(c); err != nil {
		return err
	}
	if c.GetDeletionTimestamp() == nil {
		if persistent(c) {
			return nil
		}
		uid, rv := c.GetUID(), c.GetResourceVersion()
		background := metav1.DeletePropagationBackground
		return client.IgnoreNotFound(a.C.Delete(a.Context, c, &client.DeleteOptions{PropagationPolicy: &background, Preconditions: &metav1.Preconditions{UID: &uid, ResourceVersion: &rv}}))
	}
	c.SetFinalizers(Remove(c.GetFinalizers(), Finalizer))
	return a.Update(c)
}

// Remove only this completed binding so a later allocation can bind the VM.
// A newer binding or VMI is never changed, even when the VM UID is unchanged.
func (a API) clearCompletedBinding(c *Obj) error {
	vm, err := a.Get("vms", S(c, "spec", "vmRef", "name"))
	if err != nil || !ownsBinding(c, vm) {
		return err
	}
	vmi, err := a.Get("vmis", vm.GetName())
	if err != nil {
		return err
	}
	if vmi != nil {
		return WaitError{"AwaitingCompletedVMIDeletion"}
	}
	// A one-shot VM with Always must not silently reboot without its GPU binding.
	// Preserve the stale binding until the user halts/reconfigures it.
	if S(vm, "spec", "runStrategy") != "Halted" {
		return nil
	}
	annotations := Get(vm, "spec", "template", "metadata", "annotations").(map[string]interface{})
	if raw, _ := annotations["hooks.kubevirt.io/hookSidecars"].(string); raw != "" {
		var hook interface{}
		if json.Unmarshal([]byte(raw), &hook) != nil || !Equal(hook, Hook(c)) {
			return WaitError{"CompletedBindingHookChanged"}
		}
		delete(annotations, "hooks.kubevirt.io/hookSidecars")
	}
	for _, k := range []string{"shm-channel", "shm-channel-uid", "shm-allocation", "shm-generation"} {
		delete(annotations, Group+"/"+k)
	}
	return a.Update(vm)
}

// A single-allocation channel follows the recorded VMI UID, not a name that
// KubeVirt can reuse for a later boot. Absence starts drain; it never proves detach.
func (a API) allocationEnded(c *Obj) (bool, error) {
	if persistent(c) || S(c, "status", "vmiUID") == "" || Has([]string{"Failed", "Draining"}, S(c, "status", "phase")) {
		return false, nil
	}
	vmi, err := a.Get("vmis", S(c, "spec", "vmRef", "name"))
	if err != nil {
		return false, err
	}
	if vmi == nil || string(vmi.GetUID()) != S(c, "status", "vmiUID") || vmi.GetDeletionTimestamp() != nil || Has([]string{"Succeeded", "Failed"}, S(vmi, "status", "phase")) {
		return true, a.Status(c, Map{"phase": "Draining", "reason": "VMIEnded"})
	}
	return false, nil
}

func ownsBinding(c, vm *Obj) bool {
	if vm == nil || string(vm.GetUID()) != S(c, "spec", "vmRef", "uid") || S(c, "status", "allocation") == "" || S(c, "status", "generation") == "" {
		return false
	}
	for k, v := range map[string]string{"shm-channel": c.GetName(), "shm-channel-uid": string(c.GetUID()), "shm-allocation": S(c, "status", "allocation"), "shm-generation": S(c, "status", "generation")} {
		if S(vm, "spec", "template", "metadata", "annotations", Group+"/"+k) != v {
			return false
		}
	}
	return true
}

func (a API) haltOwnedVM(c *Obj) error {
	vm, err := a.Get("vms", S(c, "spec", "vmRef", "name"))
	if err != nil || !ownsBinding(c, vm) || S(vm, "spec", "runStrategy") == "Halted" {
		return err
	}
	// VMI termination is an observation, not a request to change restart policy.
	// Only an explicit drain/delete or a failure may stop the matching runtime.
	if !B(c, "spec", "drain") && c.GetDeletionTimestamp() == nil && S(c, "status", "phase") != "Failed" {
		return nil
	}
	vmi, err := a.Get("vmis", vm.GetName())
	if err != nil {
		return err
	}
	if vmi != nil && (S(c, "status", "vmiUID") == "" || string(vmi.GetUID()) != S(c, "status", "vmiUID")) {
		return nil
	}
	spec := Get(vm, "spec").(map[string]interface{})
	delete(spec, "running")
	spec["runStrategy"] = "Halted"
	return a.Update(vm)
}
