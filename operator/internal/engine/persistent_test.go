package engine

import (
	"encoding/base64"
	"encoding/binary"
	"strings"
	"testing"
)

func TestBootLayoutMatchesProvisionABI(t *testing.T) {
	c := channel("a")
	Set(c, strings.Repeat("01", 16), "status", "allocation")
	Set(c, strings.Repeat("02", 16), "status", "generation")
	Set(c, []interface{}{strings.Repeat("03", 16)}, "status", "sessions")
	vm := obj("vms", "a", "same", "vm-a")
	config := Map{"userData": "#cloud-config\nhostname: test\n# vmweave-layout-b64: stale\n"}
	Set(vm, []interface{}{Map{"name": "cloudinit", "cloudInitNoCloud": config}}, "spec", "template", "spec", "volumes")
	if e := installBootLayout(vm, c); e != nil {
		t.Fatal(e)
	}
	config = Get(vm, "spec", "template", "spec", "volumes").([]interface{})[0].(map[string]interface{})["cloudInitNoCloud"].(map[string]interface{})
	data := config["userData"].(string)
	if strings.Count(data, "# vmweave-layout-b64:") != 1 {
		t.Fatal(data)
	}
	encoded := strings.TrimSpace(strings.Split(data, "# vmweave-layout-b64: ")[1])
	b, e := base64.StdEncoding.DecodeString(encoded)
	if e != nil || len(b) != 144 {
		t.Fatal(len(b), e)
	}
	for offset, want := range map[int]uint64{32: 67108864, 80: 4096, 96: 12416, 112: 20736, 120: 17825792, 128: 17846528, 136: 17825792} {
		if got := binary.LittleEndian.Uint64(b[offset:]); got != want {
			t.Fatalf("offset %d: %d != %d", offset, got, want)
		}
	}
	if e := installBootLayout(vm, c); e != nil || config["userData"] != data {
		t.Fatal("not idempotent", e)
	}
}
func TestPersistentStoppedRetainsChannelAndStartsOnDemand(t *testing.T) {
	c := channel("a")
	Set(c, "VM", "spec", "lifecycle")
	vm := obj("vms", "a", "same", "vm-a")
	Set(vm, "Halted", "spec", "runStrategy")
	a := fakeAPI("a", c, vm)
	for i := 0; i < 2; i++ {
		fresh, _ := a.Get("channels", "same")
		if _, e := a.PersistentPrelude(fresh); e != nil {
			t.Fatal(e)
		}
	}
	fresh, _ := a.Get("channels", "same")
	if S(fresh, "status", "phase") != "Stopped" || !Owned(fresh, vm) {
		t.Fatal(fresh)
	}
	Set(vm, "Always", "spec", "runStrategy")
	if e := a.Update(vm); e != nil {
		t.Fatal(e)
	}
	done, e := a.PersistentPrelude(fresh)
	if e != nil || done {
		t.Fatal(done, e)
	}
}
func TestPersistentVMStopDrainsRuntime(t *testing.T) {
	c := channel("a")
	Set(c, "VM", "spec", "lifecycle")
	Set(c, "Ready", "status", "phase")
	Set(c, "allocation", "status", "allocation")
	Set(c, true, "status", "everBound")
	vm := obj("vms", "a", "same", "vm-a")
	Set(vm, "Halted", "spec", "runStrategy")
	a := fakeAPI("a", c, vm)
	for i := 0; i < 2; i++ {
		fresh, _ := a.Get("channels", "same")
		if _, e := a.PersistentPrelude(fresh); e != nil {
			t.Fatal(e)
		}
	}
	fresh, _ := a.Get("channels", "same")
	if S(fresh, "status", "phase") != "Draining" {
		t.Fatal(fresh)
	}
}

func TestUnboundMissingWorkerStillRequiresDetachEvidence(t *testing.T) {
	c := channel("a")
	Set(c, "VM", "spec", "lifecycle")
	Set(c, "allocation", "status", "allocation")
	Set(c, "worker-uid", "status", "workerPodUID")
	vm := obj("vms", "a", "same", "vm-a")
	Set(vm, "Halted", "spec", "runStrategy")
	a := fakeAPI("a", c, vm)
	if e := a.Drain(c, Options{}); e != nil {
		t.Fatal(e)
	}
	fresh, _ := a.Get("channels", "same")
	if S(fresh, "status", "reason") != "AwaitingDetachEvidence" {
		t.Fatal(fresh)
	}
}
func TestFinishStopClearsRuntimeIdentityOnly(t *testing.T) {
	c := channel("a")
	Set(c, "VM", "spec", "lifecycle")
	Set(c, "Reclaimed", "status", "phase")
	Set(c, "old", "status", "allocation")
	Set(c, "old", "status", "generation")
	Set(c, true, "status", "everBound")
	a := fakeAPI("a", c)
	if e := a.FinishStop(c); e != nil {
		t.Fatal(e)
	}
	fresh, _ := a.Get("channels", "same")
	if fresh.GetUID() != c.GetUID() || S(fresh, "status", "phase") != "Stopped" || S(fresh, "status", "allocation") != "" || S(fresh, "status", "generation") != "" || B(fresh, "status", "everBound") {
		t.Fatal(fresh)
	}
	if !Equal(Get(fresh, "spec"), Get(c, "spec")) {
		t.Fatal("durable spec changed")
	}
}
