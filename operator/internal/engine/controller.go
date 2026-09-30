package engine

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"
)

type Reconciler struct {
	Client     client.Client
	Reader     client.Reader
	Namespaces map[string]bool
	Options    Options
}

func (r *Reconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	if !r.Namespaces[req.Namespace] {
		return ctrl.Result{}, nil
	}
	a := API{r.Client, r.Reader, req.Namespace, ctx}
	c, e := a.Get("channels", req.Name)
	if e != nil || c == nil {
		return ctrl.Result{}, e
	}
	e = a.Reconcile(c, r.Options)
	if e != nil {
		var wait WaitError
		var inv InvalidError
		if errors.As(e, &wait) {
			ctrl.LoggerFrom(ctx).Info("dependency pending", "reason", wait.Reason)
			return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
		}
		if errors.As(e, &inv) {
			ctrl.LoggerFrom(ctx).Error(e, "configuration rejected")
			if r.Options.Mode != "review" {
				e = a.Status(c, Map{"phase": "Failed", "reason": "InvalidConfiguration"})
			}
			return ctrl.Result{RequeueAfter: 5 * time.Second}, e
		}
		return ctrl.Result{}, e
	}
	return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
}
func (r *Reconciler) Setup(mgr ctrl.Manager) error {
	b := ctrl.NewControllerManagedBy(mgr).Named("channel").For(New("channels"))
	// Index references by name within each namespace; UID checks still happen in Reconcile.
	for _, entry := range []struct{ kind, field string }{
		{"channels", "spec.vmRef.name"}, {"channels", "spec.requestRef.name"}, {"channels", "spec.pvcRef.name"}, {"channels", "status.vmiUID"}, {"requests", "spec.profileRef.name"},
	} {
		path := strings.Split(entry.field, ".")
		if err := mgr.GetFieldIndexer().IndexField(context.Background(), New(entry.kind), entry.field, func(o client.Object) []string {
			u, ok := o.(*Obj)
			if !ok {
				return nil
			}
			v := S(u, path...)
			if v == "" {
				return nil
			}
			return []string{v}
		}); err != nil {
			return err
		}
	}
	mapEvent := handler.EnqueueRequestsFromMapFunc(r.Dependents)
	for _, k := range []string{"attachments", "pods", "pvcs", "vms", "vmis", "requests", "profiles"} {
		b = b.Watches(New(k), mapEvent)
	}
	if e := b.Complete(r); e != nil {
		return fmt.Errorf("setup: %w", e)
	}
	return nil
}

// Dependents returns only affected channel keys, always within the event namespace.
func (r *Reconciler) Dependents(ctx context.Context, o client.Object) []reconcile.Request {
	if !r.Namespaces[o.GetNamespace()] {
		return nil
	}
	u, ok := o.(*Obj)
	if !ok {
		return nil
	}
	names := map[string]bool{}
	lookup := func(kind, field, value string) []Obj {
		if value == "" {
			return nil
		}
		l := &unstructured.UnstructuredList{}
		g := kinds[kind]
		g.Kind += "List"
		l.SetGroupVersionKind(g)
		if err := r.Client.List(ctx, l, client.InNamespace(o.GetNamespace()), client.MatchingFields{field: value}); err != nil {
			ctrl.LoggerFrom(ctx).Error(err, "dependency index lookup failed")
			return nil
		}
		return l.Items
	}
	channels := func(field, value string) {
		for _, c := range lookup("channels", field, value) {
			names[c.GetName()] = true
		}
	}
	switch u.GetKind() {
	case "VirtualMachine", "VirtualMachineInstance":
		channels("spec.vmRef.name", u.GetName())
	case "PersistentVolumeClaim":
		channels("spec.pvcRef.name", u.GetName())
	case "GPURequest":
		channels("spec.requestRef.name", u.GetName())
	case "GPUProfile":
		for _, q := range lookup("requests", "spec.profileRef.name", u.GetName()) {
			channels("spec.requestRef.name", q.GetName())
		}
	case "ChannelAttachment":
		names[S(u, "spec", "channelRef", "name")] = true
	case "Pod":
		for _, ref := range u.GetOwnerReferences() {
			if ref.APIVersion == Group+"/v1alpha1" && ref.Kind == "SharedMemoryChannel" {
				names[ref.Name] = true
			}
		}
		channels("status.vmiUID", u.GetLabels()["kubevirt.io/created-by"])
	}
	out := []reconcile.Request{}
	for name := range names {
		if name != "" {
			out = append(out, reconcile.Request{NamespacedName: types.NamespacedName{Namespace: o.GetNamespace(), Name: name}})
		}
	}
	return out
}
