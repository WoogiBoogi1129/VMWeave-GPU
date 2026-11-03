package engine

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"testing"
)

func completedFixture(t *testing.T, persistentMode bool) (API, *Obj) {
	t.Helper()
	c := channel("a")
	c.SetFinalizers([]string{Finalizer})
	if persistentMode {
		Set(c, "VM", "spec", "lifecycle")
	} else {
		Set(c, "Allocation", "spec", "lifecycle")
	}
	Set(c, Map{"phase": "Released", "allocation": "old-allocation", "generation": "old-generation", "vmiUID": "old-vmi", "workerPodUID": "old-worker", "everBound": true}, "status")
	a := fakeAPI("a", c)
	if err := a.recordCompletion(c, "Released"); err != nil {
		t.Fatal(err)
	}
	return a, c
}
func addVM(t *testing.T, a API, c *Obj, bind bool, uid string) *Obj {
	t.Helper()
	vm := obj("vms", "a", "same", uid)
	Set(vm, "Always", "spec", "runStrategy")
	if bind {
		for k, v := range map[string]string{"shm-channel": c.GetName(), "shm-channel-uid": string(c.GetUID()), "shm-allocation": S(c, "status", "allocation"), "shm-generation": S(c, "status", "generation")} {
			Set(vm, v, "spec", "template", "metadata", "annotations", Group+"/"+k)
		}
	}
	if err := a.Create(vm); err != nil {
		t.Fatal(err)
	}
	return vm
}
func TestCompletedDeletionPreservesNewVMBinding(t *testing.T) {
	a, c := completedFixture(t, false)
	vm := addVM(t, a, c, true, "vm-a")
	Set(vm, "new-channel", "spec", "template", "metadata", "annotations", Group+"/shm-channel-uid")
	if err := a.Update(vm); err != nil {
		t.Fatal(err)
	}
	vmi := obj("vmis", "a", "same", "new-vmi")
	Set(vmi, "Running", "status", "phase")
	if err := a.Create(vmi); err != nil {
		t.Fatal(err)
	}
	if err := a.Delete(c); err != nil {
		t.Fatal(err)
	}
	c, _ = a.Get("channels", "same")
	if err := a.Reconcile(c, Options{}); err != nil {
		t.Fatal(err)
	}
	got, _ := a.Get("vms", "same")
	if !Equal(got.Object["spec"], vm.Object["spec"]) {
		t.Fatal("changed newer VM binding")
	}
	if c, _ := a.Get("channels", "same"); c != nil {
		t.Fatal("completion did not finalize")
	}
	if pods, _ := a.List("pods"); len(pods) != 0 {
		t.Fatal("recreated reclaim pod")
	}
}
func TestAllocationCompletionDeletesChannelAndClearsOnlyOwnBinding(t *testing.T) {
	a, c := completedFixture(t, false)
	vm := addVM(t, a, c, true, "vm-a")
	Set(vm, "Halted", "spec", "runStrategy")
	Set(vm, "keep", "spec", "template", "metadata", "annotations", "example.org/user")
	if err := a.Update(vm); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 3; i++ {
		x, _ := a.Get("channels", "same")
		if x == nil {
			break
		}
		if err := a.Reconcile(x, Options{}); err != nil {
			t.Fatal(err)
		}
	}
	if x, _ := a.Get("channels", "same"); x != nil {
		t.Fatal("allocation retained")
	}
	got, _ := a.Get("vms", "same")
	if got == nil || S(got, "spec", "runStrategy") != "Halted" || S(got, "spec", "template", "metadata", "annotations", "example.org/user") != "keep" {
		t.Fatal("VM or user configuration changed")
	}
	if S(got, "spec", "template", "metadata", "annotations", Group+"/shm-channel-uid") != "" {
		t.Fatal("stale binding retained")
	}
}
func TestCompletedReceiptCannotBeReused(t *testing.T) {
	for _, entry := range []struct{ field []string }{
		{[]string{"spec", "pvcRef", "uid"}}, {[]string{"spec", "vmRef", "uid"}}, {[]string{"status", "allocation"}}, {[]string{"status", "generation"}}, {[]string{"status", "vmiUID"}}, {[]string{"status", "workerPodUID"}}, {[]string{"status", "backend"}}, {[]string{"status", "claimUID"}}, {[]string{"status", "claimName"}},
	} {
		t.Run(entry.field[len(entry.field)-1], func(t *testing.T) {
			_, c := completedFixture(t, false)
			Set(c, "different", entry.field...)
			if completed(c) {
				t.Fatal("stale receipt accepted")
			}
		})
	}
	_, c := completedFixture(t, false)
	c.SetUID("replacement")
	if completed(c) {
		t.Fatal("replaced channel accepted")
	}
}
func TestLegacyReleasedDeletionFailsClosedWithoutVMOrPodMutation(t *testing.T) {
	a, c := completedFixture(t, false)
	Set(c, nil, "status", "completion")
	if err := a.Status(c, Map{"completion": nil}); err != nil {
		t.Fatal(err)
	}
	// Persist via a fresh instance because Status compares fields before updating.
	fresh, _ := a.Get("channels", "same")
	if err := a.Status(fresh, Map{"completion": nil}); err != nil {
		t.Fatal(err)
	}
	c = fresh
	vm := addVM(t, a, c, true, "vm-a")
	if err := a.Delete(c); err != nil {
		t.Fatal(err)
	}
	c, _ = a.Get("channels", "same")
	if err := a.Reconcile(c, Options{}); err == nil {
		t.Fatal("legacy evidence bypass")
	}
	got, _ := a.Get("vms", "same")
	if !Equal(Get(vm, "spec"), Get(got, "spec")) {
		t.Fatal("legacy delete stopped VM")
	}
	if pods, _ := a.List("pods"); len(pods) != 0 {
		t.Fatal("legacy delete recreated reclaim")
	}
}
func TestAllocationFollowsRecordedVMIAndRequiresDetach(t *testing.T) {
	for _, state := range []string{"absent", "replaced", "deleting", "Succeeded", "Failed", "Running"} {
		t.Run(state, func(t *testing.T) {
			c := channel("a")
			c.SetFinalizers([]string{Finalizer})
			Set(c, "Allocation", "spec", "lifecycle")
			Set(c, Map{"phase": "Ready", "allocation": "a", "generation": "g", "vmiUID": "old-vmi", "everBound": true}, "status")
			objects := []client.Object{c}
			if state != "absent" {
				v := obj("vmis", "a", "same", "old-vmi")
				Set(v, state, "status", "phase")
				if state == "replaced" {
					v.SetUID("new-vmi")
				}
				if state == "deleting" {
					now := metav1.Now()
					v.SetDeletionTimestamp(&now)
					v.SetFinalizers([]string{"test"})
				}
				objects = append(objects, v)
			}
			a := fakeAPI("a", objects...)
			done, err := a.allocationEnded(c)
			if err != nil {
				t.Fatal(err)
			}
			if state == "Running" {
				if done {
					t.Fatal("active VMI ended")
				}
				return
			}
			if !done {
				t.Fatal("termination missed")
			}
			x, _ := a.Get("channels", "same")
			if S(x, "status", "reason") != "VMIEnded" {
				t.Fatal(x)
			}
			if err := a.Reconcile(x, Options{}); err != nil {
				t.Fatal(err)
			}
			x, _ = a.Get("channels", "same")
			if S(x, "status", "reason") != "AwaitingDetachEvidence" {
				t.Fatal("absence inferred detach")
			}
			if completed(x) {
				t.Fatal("unproven completion")
			}
		})
	}
}
func TestDrainCannotStopReplacementVMI(t *testing.T) {
	a, c := completedFixture(t, false)
	vm := addVM(t, a, c, true, "vm-a")
	vmi := obj("vmis", "a", "same", "new-vmi")
	if err := a.Create(vmi); err != nil {
		t.Fatal(err)
	}
	Set(c, true, "spec", "drain")
	if err := a.haltOwnedVM(c); err != nil {
		t.Fatal(err)
	}
	got, _ := a.Get("vms", "same")
	if !Equal(Get(vm, "spec"), Get(got, "spec")) {
		t.Fatal("replacement VMI stopped")
	}
}
func TestExplicitDrainStopsMatchingRuntime(t *testing.T) {
	a, c := completedFixture(t, false)
	addVM(t, a, c, true, "vm-a")
	vmi := obj("vmis", "a", "same", "old-vmi")
	if err := a.Create(vmi); err != nil {
		t.Fatal(err)
	}
	Set(c, true, "spec", "drain")
	if err := a.haltOwnedVM(c); err != nil {
		t.Fatal(err)
	}
	got, _ := a.Get("vms", "same")
	if S(got, "spec", "runStrategy") != "Halted" {
		t.Fatal("matching runtime not stopped")
	}
}

func TestCompletedAlwaysVMDoesNotLoseGPUBinding(t *testing.T) {
	a, c := completedFixture(t, false)
	vm := addVM(t, a, c, true, "vm-a")
	if err := a.Reconcile(c, Options{}); err != nil {
		t.Fatal(err)
	}
	got, _ := a.Get("vms", "same")
	if !Equal(Get(vm, "spec"), Get(got, "spec")) {
		t.Fatal("Always VM could reboot without its GPU binding")
	}
}
