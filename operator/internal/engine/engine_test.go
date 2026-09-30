package engine

import (
	"context"
	"encoding/json"
	"testing"

	admissionv1 "k8s.io/api/admission/v1"
	authenticationv1 "k8s.io/api/authentication/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
)

func obj(k, ns, n, uid string) *Obj {
	o := New(k)
	o.SetNamespace(ns)
	o.SetName(n)
	o.SetUID(types.UID(uid))
	o.SetGeneration(1)
	return o
}
func fakeAPI(ns string, objects ...client.Object) API {
	s := runtime.NewScheme()
	f := fake.NewClientBuilder().WithScheme(s).WithObjects(objects...).WithStatusSubresource(New("channels"), New("attachments"), New("pods")).Build()
	return API{f, f, ns, context.Background()}
}
func channel(ns string) *Obj {
	c := obj("channels", ns, "same", "channel-"+ns)
	Set(c, Map{"vmRef": Map{"name": "same", "uid": "vm-" + ns}, "requestRef": Map{"name": "same", "uid": "request-" + ns}, "pvcRef": Map{"name": "same", "uid": "pvc-" + ns}}, "spec")
	return c
}
func TestNamespaceIsolation(t *testing.T) {
	a, b := channel("a"), channel("b")
	api := fakeAPI("a", a, b)
	x, e := api.Get("channels", "same")
	if e != nil || x.GetUID() != a.GetUID() {
		t.Fatal(x, e)
	}
	if api.Update(b) == nil {
		t.Fatal("cross namespace write allowed")
	}
	if api.Delete(b) == nil {
		t.Fatal("cross namespace delete allowed")
	}
	if _, e = api.Require("channels", Ref(b)); e == nil {
		t.Fatal("cross namespace ref accepted")
	}
}
func TestGeneralVMAllowed(t *testing.T) {
	a := fakeAPI("a")
	v := obj("vmis", "a", "normal", "vmi")
	raw, _ := json.Marshal(v.Object)
	r := admissionv1.AdmissionRequest{Namespace: "a", Kind: metav1.GroupVersionKind{Kind: "VirtualMachineInstance"}, Operation: admissionv1.Create, Object: runtime.RawExtension{Raw: raw}}
	if e := a.Validate(r, "vmweave-system", "vmweave-controller"); e != nil {
		t.Fatal(e)
	}
}
func TestManagedVMCannotRemoveBinding(t *testing.T) {
	c := channel("a")
	a := fakeAPI("a", c)
	v := obj("vmis", "a", "same", "vmi")
	v.SetOwnerReferences([]metav1.OwnerReference{{Kind: "VirtualMachine", UID: "vm-a"}})
	raw, _ := json.Marshal(v.Object)
	r := admissionv1.AdmissionRequest{Namespace: "a", Kind: metav1.GroupVersionKind{Kind: "VirtualMachineInstance"}, Operation: admissionv1.Create, Object: runtime.RawExtension{Raw: raw}}
	if a.Validate(r, "system", "controller") == nil {
		t.Fatal("missing binding allowed")
	}
}
func TestControllerIdentity(t *testing.T) {
	c := channel("a")
	Set(c, "gen", "status", "generation")
	att := obj("attachments", "a", "same-guest", "att")
	Set(att, Map{"channelRef": Ref(c), "generation": "gen"}, "spec")
	raw, _ := json.Marshal(att.Object)
	a := fakeAPI("a", c)
	r := admissionv1.AdmissionRequest{Namespace: "a", SubResource: "status", Kind: metav1.GroupVersionKind{Kind: "ChannelAttachment"}, Object: runtime.RawExtension{Raw: raw}}
	for _, user := range []string{"system:serviceaccount:other:vmweave-controller", "system:serviceaccount:a:vmweave-controller", "system:serviceaccount:other:same-worker"} {
		r.UserInfo = authenticationv1.UserInfo{Username: user}
		if a.Validate(r, "vmweave-system", "vmweave-controller") == nil {
			t.Fatal("foreign reporter accepted", user)
		}
	}
	r.UserInfo.Username = "system:serviceaccount:vmweave-system:vmweave-controller"
	if e := a.Validate(r, "vmweave-system", "vmweave-controller"); e != nil {
		t.Fatal(e)
	}
}
func TestMissingEvidenceNeverReclaims(t *testing.T) {
	c := channel("a")
	c.SetFinalizers([]string{Finalizer})
	Set(c, Map{"phase": "Draining", "everBound": true, "generation": "g", "allocation": "a"}, "status")
	a := fakeAPI("a", c)
	if e := a.Reconcile(c, Options{Mode: "active"}); e != nil {
		t.Fatal(e)
	}
	stored, e := a.Get("channels", c.GetName())
	if e != nil || S(stored, "status", "reason") != "AwaitingDetachEvidence" {
		t.Fatal(stored, e)
	}
	pods, e := a.List("pods")
	if e != nil || len(pods) != 0 {
		t.Fatal("created reclaim without evidence", e)
	}
}
func TestReleasedIdle(t *testing.T) {
	c := channel("a")
	Set(c, "Released", "status", "phase")
	a := fakeAPI("a", c)
	if e := a.Reconcile(c, Options{Mode: "active"}); e != nil {
		t.Fatal(e)
	}
	x, _ := a.Get("channels", c.GetName())
	if len(x.GetFinalizers()) != 0 {
		t.Fatal("released resource mutated")
	}
}
func TestReplacedWorkerRejected(t *testing.T) {
	c := channel("a")
	Set(c, "old", "status", "workerPodUID")
	p := Child("pods", "same-worker", c)
	p.SetUID("new")
	a := fakeAPI("a", c, p)
	if _, e := a.Worker(c, nil, Options{}); e == nil {
		t.Fatal("replacement accepted")
	}
}
func TestReviewNoWorkloads(t *testing.T) {
	c := channel("a")
	a := fakeAPI("a", c)
	if e := a.Reconcile(c, Options{Mode: "review"}); e != nil {
		t.Fatal(e)
	}
	x, _ := a.Get("channels", c.GetName())
	if S(x, "status", "phase") != "ReviewOnly" || len(x.GetFinalizers()) != 0 {
		t.Fatal(x)
	}
	pods, e := a.List("pods")
	if e != nil || len(pods) > 0 {
		t.Fatal(e)
	}
}
func TestTerminalRequiresEveryContainer(t *testing.T) {
	p := obj("pods", "a", "p", "uid")
	Set(p, Map{"containers": []interface{}{Map{"name": "main"}}}, "spec")
	Set(p, Map{"phase": "Failed"}, "status")
	if Terminal(p) {
		t.Fatal("missing status accepted")
	}
	Set(p, []interface{}{Map{"name": "main", "state": Map{"terminated": Map{"exitCode": int64(0)}}}}, "status", "containerStatuses")
	if !Terminal(p) {
		t.Fatal("terminal status rejected")
	}
}

func TestWorkerMappingUsesIntegerGeneration(t *testing.T) {
	c := channel("a")
	Set(c, "g", "status", "generation")
	Set(c, "same-unique", "status", "resourcePrefix")
	p := obj("pods", "a", "same-unique-worker", "worker-uid")
	att := obj("attachments", "a", "same-guest", "att")
	Set(att, Map{"channelRef": Ref(c), "generation": "g", "role": "guest", "holderUID": "vmi"}, "spec")
	Set(att, Map{"phase": "Mapped", "reporterPodUID": "worker-uid", "observedGeneration": int64(1)}, "status")
	raw, _ := json.Marshal(att.Object)
	a := fakeAPI("a", c, p)
	r := admissionv1.AdmissionRequest{Namespace: "a", SubResource: "status", Kind: metav1.GroupVersionKind{Kind: "ChannelAttachment"}, Object: runtime.RawExtension{Raw: raw}, UserInfo: authenticationv1.UserInfo{Username: "system:serviceaccount:a:same-unique-worker"}}
	if e := a.Validate(r, "system", "controller"); e != nil {
		t.Fatal("valid mapping rejected", e)
	}
	Set(att, int64(2), "status", "observedGeneration")
	r.Object.Raw, _ = json.Marshal(att.Object)
	if a.Validate(r, "system", "controller") == nil {
		t.Fatal("stale generation accepted")
	}
}

func TestReleasedDeletionRequiresConfirmedReclaim(t *testing.T) {
	c := channel("a")
	c.SetFinalizers([]string{Finalizer})
	Set(c, Map{"phase": "Released", "everBound": true, "generation": "g"}, "status")
	objects := []client.Object{c}
	for _, role := range []string{"guest", "worker"} {
		att := obj("attachments", "a", "same-"+role, role)
		Set(att, Map{"channelRef": Ref(c), "generation": "g"}, "spec")
		Set(att, Map{"phase": "Detached", "observedGeneration": int64(1)}, "status")
		objects = append(objects, att)
	}
	reclaim := Child("pods", "same-reclaim", c)
	Set(reclaim, "Succeeded", "status", "phase")
	objects = append(objects, reclaim)
	a := fakeAPI("a", objects...)
	if e := a.Delete(c); e != nil {
		t.Fatal(e)
	}
	c, _ = a.Get("channels", "same")
	if e := a.Reconcile(c, Options{Mode: "active"}); e != nil {
		t.Fatal(e)
	}
	c, _ = a.Get("channels", "same")
	if c != nil {
		t.Fatal("released finalizer retained")
	}
}

func TestDependencyIndexIsScopedToNamespaceAndVM(t *testing.T) {
	a, b, c := channel("a"), channel("b"), channel("a")
	c.SetName("different")
	c.SetUID("different")
	Set(c, "other", "spec", "vmRef", "name")
	f := fake.NewClientBuilder().WithScheme(runtime.NewScheme()).WithObjects(a, b, c).WithIndex(New("channels"), "spec.vmRef.name", func(o client.Object) []string { return []string{S(o.(*Obj), "spec", "vmRef", "name")} }).Build()
	r := Reconciler{Client: f, Namespaces: map[string]bool{"a": true, "b": true}}
	requests := r.Dependents(context.Background(), obj("vms", "a", "same", "vm-a"))
	if len(requests) != 1 || requests[0].Namespace != "a" || requests[0].Name != "same" {
		t.Fatal(requests)
	}
	if got := r.Dependents(context.Background(), obj("vms", "outside", "same", "vm")); len(got) > 0 {
		t.Fatal(got)
	}
}

func TestChildNamesDoNotCollideWithPreservedHistory(t *testing.T) {
	c := channel("a")
	old := c.DeepCopy()
	old.SetUID("old-uid")
	legacy := Child("pods", "same-prepare", old)
	a := fakeAPI("a", c, legacy)
	Set(c, allocationPrefix(c), "status", "resourcePrefix")
	name := ResourceName(c, "prepare")
	if name == legacy.GetName() || len(name) > 63 {
		t.Fatal(name)
	}
	if _, e := a.Ensure(Child("pods", name, c), c); e != nil {
		t.Fatal(e)
	}
	saved, _ := a.Get("pods", legacy.GetName())
	if !Owned(saved, old) {
		t.Fatal("historical object changed")
	}
}
