package engine

import "fmt"

func (a API) Worker(c, p *Obj, opts Options) (*Obj, error) {
	name := ResourceName(c, "worker")
	if uid := S(c, "status", "workerPodUID"); uid != "" {
		w, e := a.Get("pods", name)
		if e != nil {
			return nil, e
		}
		if w == nil {
			return nil, nil
		}
		if string(w.GetUID()) != uid || !Owned(w, c) {
			return nil, invalid("worker generation changed")
		}
		return w, nil
	}
	sa := Child("serviceaccounts", name, c)
	if _, e := a.Ensure(sa, c); e != nil {
		return nil, e
	}
	role := Child("roles", name, c)
	Set(role, []interface{}{Map{"apiGroups": cmds(Group), "resources": cmds("sharedmemorychannels"), "resourceNames": cmds(c.GetName()), "verbs": cmds("get")}, Map{"apiGroups": cmds(Group), "resources": cmds("channelattachments", "channelattachments/status"), "resourceNames": cmds(c.GetName()+"-guest", c.GetName()+"-worker"), "verbs": cmds("get", "update")}}, "rules")
	if _, e := a.Ensure(role, c); e != nil {
		return nil, e
	}
	rb := Child("rolebindings", name, c)
	Set(rb, Map{"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": name}, "roleRef")
	Set(rb, []interface{}{Map{"kind": "ServiceAccount", "name": name, "namespace": a.Namespace}}, "subjects")
	if _, e := a.Ensure(rb, c); e != nil {
		return nil, e
	}
	w := Pod(c, name, S(c, "spec", "workerImage"), cmds("python3", "/opt/flyt/control/supervisor.py"), opts)
	w.SetFinalizers([]string{DetachFinalizer})
	w.SetAnnotations(map[string]string{DetachChannel: string(c.GetUID()), "nvidia.com/use-gpuuuid": S(c, "status", "gpuUUID")})
	Set(w, name, "spec", "serviceAccountName")
	Set(w, true, "spec", "automountServiceAccountToken")
	Set(w, S(p, "spec", "schedulerName"), "spec", "schedulerName")
	if r := S(p, "spec", "runtimeClass"); r != "" {
		Set(w, r, "spec", "runtimeClassName")
	}
	env := []interface{}{}
	for k, v := range map[string]interface{}{"FLYT_ALLOCATION": S(c, "status", "allocation"), "FLYT_GPU_UUID": S(c, "status", "gpuUUID"), "FLYT_RESOURCE_BACKEND": "hami", "FLYT_MEMORY_BYTES": N(c, "status", "memoryMiB") * 1048576, "FLYT_SESSIONS": N(c, "spec", "sessions"), "FLYT_CHANNEL_NAME": c.GetName(), "FLYT_CHANNEL_UID": string(c.GetUID()), "FLYT_GENERATION": S(c, "status", "generation"), "FLYT_NAMESPACE": a.Namespace, "VMWEAVE_API_GROUP": Group} {
		env = append(env, Map{"name": k, "value": fmt.Sprint(v)})
	}
	env = append(env, Map{"name": "FLYT_POD_UID", "valueFrom": Map{"fieldRef": Map{"fieldPath": "metadata.uid"}}})
	containers := Get(w, "spec", "containers").([]interface{})
	container := containers[0].(map[string]interface{})
	container["env"] = env
	quota := Map{"nvidia.com/gpu": int64(1), "nvidia.com/gpumem": N(c, "status", "memoryMiB"), "nvidia.com/gpucores": N(c, "status", "compute")}
	container["resources"] = Map{"requests": quota, "limits": quota}
	container["readinessProbe"] = Map{"exec": Map{"command": cmds("test", "-f", "/tmp/flyt-worker-ready")}, "periodSeconds": int64(2)}
	return a.Ensure(w, c)
}
func (a API) Drain(c *Obj, opts Options) error {
	vm, e := a.Get("vms", S(c, "spec", "vmRef", "name"))
	if e != nil {
		return e
	}
	if vm != nil && string(vm.GetUID()) == S(c, "spec", "vmRef", "uid") && S(vm, "spec", "runStrategy") != "Halted" {
		spec := Get(vm, "spec").(map[string]interface{})
		delete(spec, "running")
		spec["runStrategy"] = "Halted"
		if e = a.Update(vm); e != nil {
			return e
		}
	}
	w, e := a.Get("pods", ResourceName(c, "worker"))
	if e != nil {
		return e
	}
	if w != nil && Owned(w, c) && w.GetDeletionTimestamp() == nil {
		if e = a.Delete(w); e != nil {
			return e
		}
	}
	complete := B(c, "status", "everBound")
	for _, role := range []string{"guest", "worker"} {
		att, e := a.Get("attachments", c.GetName()+"-"+role)
		if e != nil {
			return e
		}
		if att == nil || !Equal(Get(att, "spec", "channelRef"), Ref(c)) || S(att, "status", "phase") != "Detached" || N(att, "status", "observedGeneration") != att.GetGeneration() || S(att, "spec", "generation") != S(c, "status", "generation") {
			complete = false
		}
	}
	if !complete {
		return a.Status(c, Map{"phase": "Draining", "reason": "AwaitingDetachEvidence"})
	}
	cleanup, e := a.Get("pods", ResourceName(c, "reclaim"))
	if e != nil {
		return e
	}
	if cleanup == nil {
		ns, e := a.Get("namespaces", a.Namespace)
		if e != nil {
			return e
		}
		if ns == nil || ns.GetDeletionTimestamp() != nil {
			return a.Status(c, Map{"phase": "Draining", "reason": "NamespaceTerminatingReclaimBlocked"})
		}
		cleanup, e = a.Ensure(Pod(c, ResourceName(c, "reclaim"), S(c, "spec", "image"), cmds("python3", "/opt/flyt/control/reclaim.py", "--root", "/flyt-channel", "--allocation", S(c, "status", "allocation"), "--generation", S(c, "status", "generation")), opts), c)
		if e != nil {
			return e
		}
	} else if !Owned(cleanup, c) {
		return invalid("foreign reclaim pod")
	}
	if S(cleanup, "status", "phase") != "Succeeded" {
		return a.Status(c, Map{"phase": "Draining", "reason": "ReclamationPending"})
	}
	if e = a.Status(c, Map{"phase": "Released", "reason": "DetachAndReclamationConfirmed"}); e != nil {
		return e
	}
	if c.GetDeletionTimestamp() != nil {
		fresh, e := a.Get("channels", c.GetName())
		if e != nil || fresh == nil {
			return e
		}
		fresh.SetFinalizers(Remove(fresh.GetFinalizers(), Finalizer))
		return a.Update(fresh)
	}
	return nil
}
