package engine

import (
	"encoding/json"
	"fmt"
	admissionv1 "k8s.io/api/admission/v1"
)

func (a API) Validate(r admissionv1.AdmissionRequest, controllerNS, controllerSA string) error {
	if r.Namespace == "" || r.Namespace != a.Namespace {
		return invalid("request namespace mismatch")
	}
	o := &Obj{}
	if e := o.UnmarshalJSON(r.Object.Raw); e != nil {
		return e
	}
	if o.GetNamespace() != r.Namespace {
		return invalid("object namespace mismatch")
	}
	switch r.Kind.Kind {
	case "SharedMemoryChannel":
		q, e := a.Get("requests", S(o, "spec", "requestRef", "name"))
		if e != nil {
			return e
		}
		if q != nil && string(q.GetUID()) == S(o, "spec", "requestRef", "uid") {
			if !Equal(Get(q, "spec", "vmRef"), Get(o, "spec", "vmRef")) {
				return invalid("request references different VM")
			}
			p, e := a.Get("profiles", S(q, "spec", "profileRef", "name"))
			if e != nil {
				return e
			}
			if p != nil && string(p.GetUID()) == S(q, "spec", "profileRef", "uid") {
				if !B(p, "spec", "approved") || S(o, "spec", "workerImage") != S(p, "spec", "workerImage") || N(o, "spec", "sessions") > N(p, "spec", "maxClients") {
					return invalid("profile does not approve worker/sessions")
				}
			}
		}
		return nil
	case "ChannelAttachment":
		if r.SubResource != "status" {
			return invalid("unexpected attachment operation")
		}
		c, e := a.Get("channels", S(o, "spec", "channelRef", "name"))
		if e != nil {
			return e
		}
		if c == nil || string(c.GetUID()) != S(o, "spec", "channelRef", "uid") || S(c, "status", "generation") != S(o, "spec", "generation") {
			return invalid("stale attachment")
		}
		if r.UserInfo.Username == "system:serviceaccount:"+controllerNS+":"+controllerSA {
			return nil
		}
		if r.UserInfo.Username != "system:serviceaccount:"+a.Namespace+":"+ResourceName(c, "worker") {
			return invalid("unauthorized attachment reporter")
		}
		p, e := a.Get("pods", ResourceName(c, "worker"))
		if e != nil {
			return e
		}
		if p == nil || string(p.GetUID()) != S(o, "status", "reporterPodUID") || N(o, "status", "observedGeneration") != o.GetGeneration() {
			return invalid("stale reporter")
		}
		if S(o, "spec", "role") == "guest" && S(o, "status", "phase") != "Mapped" {
			return invalid("worker cannot attest guest detach")
		}
		if S(o, "spec", "role") == "worker" && S(o, "spec", "holderUID") != string(p.GetUID()) {
			return invalid("wrong holder")
		}
		if !Has([]string{"Mapped", "Detached"}, S(o, "status", "phase")) {
			return invalid("invalid attachment phase")
		}
		old := &Obj{}
		_ = old.UnmarshalJSON(r.OldObject.Raw)
		if S(old, "status", "phase") == "Detached" {
			return invalid("terminal attachment")
		}
		return nil
	case "VirtualMachineInstanceMigration":
		v, e := a.Get("vmis", S(o, "spec", "vmiName"))
		if e != nil {
			return e
		}
		if v == nil {
			return nil
		}
		managed, e := a.managed(v)
		if e != nil {
			return e
		}
		if managed {
			return invalid("SHM migration unsupported")
		}
		return nil
	case "VirtualMachineInstance":
		old := &Obj{}
		if len(r.OldObject.Raw) > 0 {
			if e := old.UnmarshalJSON(r.OldObject.Raw); e != nil {
				return e
			}
		}
		managed, e := a.managed(o)
		if e != nil {
			return e
		}
		if !managed && len(r.OldObject.Raw) > 0 {
			managed, e = a.managed(old)
			if e != nil {
				return e
			}
		}
		if !managed {
			return nil
		}
		if r.Operation == admissionv1.Update {
			for _, k := range []string{Group + "/shm-channel", Group + "/shm-channel-uid", Group + "/shm-allocation", Group + "/shm-generation", "hooks.kubevirt.io/hookSidecars"} {
				if o.GetAnnotations()[k] != old.GetAnnotations()[k] {
					return invalid("active VMI binding immutable")
				}
			}
			if !Equal(Get(o, "spec", "nodeSelector"), Get(old, "spec", "nodeSelector")) {
				return invalid("active placement immutable")
			}
			return nil
		}
		name := o.GetAnnotations()[Group+"/shm-channel"]
		if name == "" {
			return invalid("managed VM requires channel binding")
		}
		c, e := a.Get("channels", name)
		if e != nil {
			return e
		}
		if c == nil || c.GetDeletionTimestamp() != nil || B(c, "spec", "drain") || S(c, "status", "phase") != "BackingReady" || S(c, "status", "vmiUID") != "" {
			return invalid("channel unavailable")
		}
		for k, v := range map[string]string{"shm-channel-uid": string(c.GetUID()), "shm-allocation": S(c, "status", "allocation"), "shm-generation": S(c, "status", "generation")} {
			if o.GetAnnotations()[Group+"/"+k] != v {
				return invalid("binding identity mismatch")
			}
		}
		owner := false
		for _, ref := range o.GetOwnerReferences() {
			if string(ref.UID) == S(c, "spec", "vmRef", "uid") {
				owner = true
			}
		}
		if !owner {
			return invalid("VM owner mismatch")
		}
		if S(o, "spec", "nodeSelector", "kubernetes.io/hostname") != S(c, "status", "nodeName") {
			return invalid("co-placement required")
		}
		var hook interface{}
		if json.Unmarshal([]byte(o.GetAnnotations()["hooks.kubevirt.io/hookSidecars"]), &hook) != nil || !Equal(hook, Hook(c)) {
			return invalid("hook changed")
		}
		return nil
	}
	return fmt.Errorf("unsupported admission kind %s", r.Kind.Kind)
}
func (a API) managed(o *Obj) (bool, error) {
	for _, prefix := range []string{Group, "flyt.dev"} {
		if o.GetAnnotations()[prefix+"/shm-channel"] != "" {
			return true, nil
		}
	}
	cs, e := a.List("channels")
	if e != nil {
		return false, e
	}
	for _, c := range cs {
		if S(&c, "status", "phase") == "Released" {
			continue
		}
		for _, r := range o.GetOwnerReferences() {
			if r.Kind == "VirtualMachine" && string(r.UID) == S(&c, "spec", "vmRef", "uid") {
				return true, nil
			}
		}
	}
	return false, nil
}
