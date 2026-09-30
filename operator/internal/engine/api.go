package engine

import (
	"context"
	"fmt"
	"reflect"
	"strings"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

const Group = "vmweave.io"
const Finalizer = Group + "/shm-detach"
const DetachFinalizer = Group + "/detach-observation"
const DetachChannel = Group + "/detach-channel-uid"

type Obj = unstructured.Unstructured
type Map = map[string]interface{}

var kinds = map[string]schema.GroupVersionKind{
	"channels": {Group: Group, Version: "v1alpha1", Kind: "SharedMemoryChannel"}, "attachments": {Group: Group, Version: "v1alpha1", Kind: "ChannelAttachment"},
	"requests": {Group: Group, Version: "v1alpha1", Kind: "GPURequest"}, "profiles": {Group: Group, Version: "v1alpha1", Kind: "GPUProfile"},
	"vms": {Group: "kubevirt.io", Version: "v1", Kind: "VirtualMachine"}, "vmis": {Group: "kubevirt.io", Version: "v1", Kind: "VirtualMachineInstance"},
	"pods": {Group: "", Version: "v1", Kind: "Pod"}, "pvcs": {Group: "", Version: "v1", Kind: "PersistentVolumeClaim"}, "pvs": {Group: "", Version: "v1", Kind: "PersistentVolume"},
	"nodes": {Group: "", Version: "v1", Kind: "Node"}, "namespaces": {Group: "", Version: "v1", Kind: "Namespace"}, "serviceaccounts": {Group: "", Version: "v1", Kind: "ServiceAccount"},
	"roles": {Group: "rbac.authorization.k8s.io", Version: "v1", Kind: "Role"}, "rolebindings": {Group: "rbac.authorization.k8s.io", Version: "v1", Kind: "RoleBinding"},
}

func New(kind string) *Obj { o := &Obj{}; o.SetGroupVersionKind(kinds[kind]); return o }
func Get(o *Obj, p ...string) interface{} {
	if o == nil {
		return nil
	}
	v, _, _ := unstructured.NestedFieldNoCopy(o.Object, p...)
	return v
}
func S(o *Obj, p ...string) string { v, _ := Get(o, p...).(string); return v }
func B(o *Obj, p ...string) bool   { v, _ := Get(o, p...).(bool); return v }
func N(o *Obj, p ...string) int64 {
	switch v := Get(o, p...).(type) {
	case int64:
		return v
	case float64:
		return int64(v)
	case int:
		return int64(v)
	}
	return 0
}
func Set(o *Obj, v interface{}, p ...string) {
	if err := unstructured.SetNestedField(o.Object, v, p...); err != nil {
		panic(err)
	}
}
func Ref(o *Obj) Map              { return Map{"name": o.GetName(), "uid": string(o.GetUID())} }
func Equal(a, b interface{}) bool { return reflect.DeepEqual(a, b) }
func Has(xs []string, s string) bool {
	for _, x := range xs {
		if x == s {
			return true
		}
	}
	return false
}
func Remove(xs []string, s string) []string {
	out := []string{}
	for _, x := range xs {
		if x != s {
			out = append(out, x)
		}
	}
	return out
}

type WaitError struct{ Reason string }

func (e WaitError) Error() string { return e.Reason }

type InvalidError struct{ Reason string }

func (e InvalidError) Error() string { return e.Reason }
func invalid(s string) error         { return InvalidError{s} }

type API struct {
	C         client.Client
	R         client.Reader
	Namespace string
	Context   context.Context
}

func (a API) Get(k, n string) (*Obj, error) {
	o := New(k)
	ns := a.Namespace
	if k == "pvs" || k == "nodes" || k == "namespaces" {
		ns = ""
	}
	err := a.R.Get(a.Context, types.NamespacedName{Namespace: ns, Name: n}, o)
	if apierrors.IsNotFound(err) {
		return nil, nil
	}
	return o, err
}
func (a API) List(k string) ([]Obj, error) {
	l := &unstructured.UnstructuredList{}
	g := kinds[k]
	g.Kind += "List"
	l.SetGroupVersionKind(g)
	err := a.C.List(a.Context, l, client.InNamespace(a.Namespace))
	return l.Items, err
}
func (a API) check(o *Obj) error {
	if a.Namespace == "" || o.GetNamespace() != a.Namespace {
		return fmt.Errorf("namespace mismatch: context=%s object=%s", a.Namespace, o.GetNamespace())
	}
	return nil
}
func (a API) Create(o *Obj) error {
	if err := a.check(o); err != nil {
		return err
	}
	return a.C.Create(a.Context, o)
}
func (a API) Update(o *Obj) error {
	if err := a.check(o); err != nil {
		return err
	}
	return a.C.Update(a.Context, o)
}
func (a API) Status(o *Obj, v Map) error {
	if err := a.check(o); err != nil {
		return err
	}
	changed := false
	for k, x := range v {
		if !Equal(Get(o, "status", k), x) {
			changed = true
			Set(o, x, "status", k)
		}
	}
	if !changed {
		return nil
	}
	return a.C.Status().Update(a.Context, o)
}
func (a API) Delete(o *Obj) error {
	if err := a.check(o); err != nil {
		return err
	}
	uid, rv := o.GetUID(), o.GetResourceVersion()
	return client.IgnoreNotFound(a.C.Delete(a.Context, o, &client.DeleteOptions{Preconditions: &metav1.Preconditions{UID: &uid, ResourceVersion: &rv}}))
}
func (a API) Require(k string, r interface{}) (*Obj, error) {
	m, ok := r.(map[string]interface{})
	if !ok {
		return nil, invalid("invalid reference")
	}
	n, _ := m["name"].(string)
	uid, _ := m["uid"].(string)
	o, err := a.Get(k, n)
	if err != nil {
		return nil, err
	}
	if o == nil {
		return nil, WaitError{k + " " + n + " unavailable"}
	}
	if uid == "" || string(o.GetUID()) != uid || o.GetDeletionTimestamp() != nil {
		return nil, invalid(k + " identity unavailable")
	}
	return o, nil
}
func Owned(o, c *Obj) bool {
	if o.GetNamespace() != c.GetNamespace() {
		return false
	}
	for _, r := range o.GetOwnerReferences() {
		if r.UID == c.GetUID() {
			return true
		}
	}
	return false
}
func Child(k, n string, c *Obj) *Obj {
	o := New(k)
	o.SetName(n)
	o.SetNamespace(c.GetNamespace())
	o.SetLabels(map[string]string{Group + "/channel": c.GetName()})
	yes := true
	o.SetOwnerReferences([]metav1.OwnerReference{{APIVersion: c.GetAPIVersion(), Kind: c.GetKind(), Name: c.GetName(), UID: c.GetUID(), Controller: &yes, BlockOwnerDeletion: &yes}})
	return o
}
func (a API) Ensure(o, c *Obj) (*Obj, error) {
	old := &Obj{}
	old.SetGroupVersionKind(o.GroupVersionKind())
	err := a.R.Get(a.Context, client.ObjectKeyFromObject(o), old)
	if err == nil {
		if !Owned(old, c) {
			return nil, invalid("same-name foreign object")
		}
		return old, nil
	}
	if !apierrors.IsNotFound(err) {
		return nil, err
	}
	if err = a.Create(o); err != nil {
		return nil, err
	}
	return o, nil
}

// New allocations use a UID-qualified prefix so legacy API children cannot collide.
// Missing status keeps names compatible with channels created before this field existed.
func ResourceName(c *Obj, role string) string {
	prefix := S(c, "status", "resourcePrefix")
	if prefix == "" {
		prefix = c.GetName()
	}
	return prefix + "-" + role
}
func allocationPrefix(c *Obj) string {
	name := c.GetName()
	if len(name) > 40 {
		name = name[:40]
	}
	name = strings.TrimRight(name, "-")
	uid := strings.ReplaceAll(string(c.GetUID()), "-", "")
	if len(uid) > 12 {
		uid = uid[:12]
	}
	return name + "-" + uid
}
