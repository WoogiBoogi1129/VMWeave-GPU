package engine

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

type Options struct {
	Mode        string
	Tolerations []interface{}
}

func randomID() string {
	b := make([]byte, 16)
	if _, e := rand.Read(b); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b)
}
func Pod(c *Obj, name, image string, command []interface{}, opts Options) *Obj {
	o := Child("pods", name, c)
	Set(o, Map{"restartPolicy": "Never", "automountServiceAccountToken": false, "tolerations": opts.Tolerations, "nodeSelector": Map{"kubernetes.io/hostname": S(c, "status", "nodeName")}, "securityContext": Map{"runAsUser": N(c, "spec", "uid"), "runAsGroup": N(c, "spec", "gid"), "fsGroup": N(c, "spec", "gid")}, "containers": []interface{}{Map{"name": "main", "image": image, "command": command, "volumeMounts": []interface{}{Map{"name": "channel", "mountPath": "/flyt-channel"}}}}, "volumes": []interface{}{Map{"name": "channel", "persistentVolumeClaim": Map{"claimName": S(c, "spec", "pvcRef", "name")}}}}, "spec")
	return o
}
func cmds(xs ...string) []interface{} {
	r := []interface{}{}
	for _, x := range xs {
		r = append(r, x)
	}
	return r
}
func memory(s string) (int64, error) {
	unit := int64(1)
	if strings.HasSuffix(s, "Gi") {
		unit = 1024
	} else if !strings.HasSuffix(s, "Mi") {
		return 0, invalid("integer Mi/Gi memory required")
	}
	v, e := strconv.ParseInt(s[:len(s)-2], 10, 64)
	if e != nil || v < 1 || v > 1048576 {
		return 0, invalid("invalid memory")
	}
	return v * unit, nil
}
func (a API) deps(c *Obj) (vm, q, p, pvc *Obj, err error) {
	if vm, err = a.Require("vms", Get(c, "spec", "vmRef")); err != nil {
		return
	}
	if q, err = a.Require("requests", Get(c, "spec", "requestRef")); err != nil {
		return
	}
	if p, err = a.Require("profiles", Get(q, "spec", "profileRef")); err != nil {
		return
	}
	if pvc, err = a.Require("pvcs", Get(c, "spec", "pvcRef")); err != nil {
		return
	}
	if !Equal(Get(q, "spec", "vmRef"), Get(c, "spec", "vmRef")) || !B(p, "spec", "approved") {
		err = invalid("request/profile not approved")
		return
	}
	if S(c, "spec", "workerImage") != S(p, "spec", "workerImage") || N(c, "spec", "sessions") > N(p, "spec", "maxClients") {
		err = invalid("worker image/session count not approved")
		return
	}
	if N(q, "spec", "count") != 1 || N(q, "spec", "compute") < 1 || N(q, "spec", "compute") > N(p, "spec", "cores") {
		err = invalid("compute quota invalid")
		return
	}
	m, e := memory(S(q, "spec", "memory"))
	if e != nil {
		err = e
		return
	}
	if m > N(p, "spec", "memoryMiB") {
		err = invalid("memory quota exceeds profile")
		return
	}
	if mode := S(pvc, "spec", "volumeMode"); mode != "" && mode != "Filesystem" {
		err = invalid("filesystem PVC required")
	}
	return
}
func (a API) checkPV(pvc *Obj, node string) error {
	v := S(pvc, "spec", "volumeName")
	if v == "" {
		return WaitError{"PVC not bound"}
	}
	pv, e := a.Get("pvs", v)
	if e != nil {
		return e
	}
	if pv == nil || Get(pv, "spec", "local") == nil {
		return invalid("local filesystem PV required")
	}
	terms, _ := Get(pv, "spec", "nodeAffinity", "required", "nodeSelectorTerms").([]interface{})
	if len(terms) == 0 {
		return invalid("local PV node affinity required")
	}
	for _, t := range terms {
		m, _ := t.(map[string]interface{})
		es, _ := m["matchExpressions"].([]interface{})
		found := false
		for _, e := range es {
			x, _ := e.(map[string]interface{})
			if x["key"] == "kubernetes.io/hostname" && x["operator"] == "In" && Equal(x["values"], []interface{}{node}) {
				found = true
			}
		}
		if !found {
			return invalid("PV not pinned to profile node")
		}
	}
	return nil
}
func (a API) Reconcile(c *Obj, opts Options) error {
	if c.GetNamespace() != a.Namespace {
		return invalid("channel namespace mismatch")
	}
	if opts.Mode == "review" {
		return a.Review(c)
	}
	if S(c, "status", "phase") == "Released" && c.GetDeletionTimestamp() == nil {
		return nil
	}
	protected, e := a.Observe(c)
	if e != nil {
		return e
	}
	if !Has(c.GetFinalizers(), Finalizer) {
		if c.GetDeletionTimestamp() != nil {
			return nil
		}
		c.SetFinalizers(append(c.GetFinalizers(), Finalizer))
		return a.Update(c)
	}
	if c.GetDeletionTimestamp() != nil || B(c, "spec", "drain") || Has([]string{"Failed", "Draining", "Released"}, S(c, "status", "phase")) {
		return a.Drain(c, opts)
	}
	vm, q, p, pvc, e := a.deps(c)
	if e != nil {
		return e
	}
	if S(c, "status", "allocation") == "" {
		ns, e := a.Get("namespaces", a.Namespace)
		if e != nil {
			return e
		}
		if ns == nil || ns.GetDeletionTimestamp() != nil {
			return WaitError{"NamespaceTerminating"}
		}
		vmi, e := a.Get("vmis", vm.GetName())
		if e != nil {
			return e
		}
		if vmi != nil || S(vm, "spec", "runStrategy") != "Halted" {
			return invalid("VM must initially be Halted without VMI")
		}
		m, _ := memory(S(q, "spec", "memory"))
		sessions := []interface{}{}
		for i := int64(0); i < N(c, "spec", "sessions"); i++ {
			sessions = append(sessions, randomID())
		}
		return a.Status(c, Map{"phase": "Reserved", "allocation": randomID(), "generation": randomID(), "sessions": sessions, "nodeName": S(p, "spec", "nodeName"), "gpuUUID": S(p, "spec", "gpuUUID"), "memoryMiB": m, "compute": N(q, "spec", "compute"), "requestGeneration": q.GetGeneration(), "profileGeneration": p.GetGeneration(), "resourcePrefix": allocationPrefix(c)})
	}
	if N(c, "status", "requestGeneration") != q.GetGeneration() || N(c, "status", "profileGeneration") != p.GetGeneration() {
		return invalid("frozen request/profile changed")
	}
	command := cmds("python3", "/opt/flyt/control/provision.py", "--root", "/flyt-channel", "--allocation", S(c, "status", "allocation"), "--generation", S(c, "status", "generation"), "--uid", fmt.Sprint(N(c, "spec", "uid")), "--gid", fmt.Sprint(N(c, "spec", "gid")))
	ss, _ := Get(c, "status", "sessions").([]interface{})
	for _, s := range ss {
		command = append(command, "--session", s)
	}
	prep, e := a.Ensure(Pod(c, ResourceName(c, "prepare"), S(c, "spec", "image"), command, opts), c)
	if e != nil {
		return e
	}
	if S(prep, "status", "phase") == "Failed" {
		return invalid("provision failed")
	}
	if S(prep, "status", "phase") != "Succeeded" {
		return nil
	}
	if e = a.checkPV(pvc, S(c, "status", "nodeName")); e != nil {
		return e
	}
	if S(vm, "spec", "template", "metadata", "annotations", Group+"/shm-channel") == "" {
		// Never take over an old API allocation implicitly.
		if S(vm, "spec", "template", "metadata", "annotations", "flyt.dev/shm-channel") != "" {
			return invalid("legacy VM binding must be migrated while halted")
		}
		for k, v := range map[string]string{"shm-channel": c.GetName(), "shm-channel-uid": string(c.GetUID()), "shm-allocation": S(c, "status", "allocation"), "shm-generation": S(c, "status", "generation")} {
			Set(vm, v, "spec", "template", "metadata", "annotations", Group+"/"+k)
		}
		hook, _ := json.Marshal(Hook(c))
		Set(vm, string(hook), "spec", "template", "metadata", "annotations", "hooks.kubevirt.io/hookSidecars")
		Set(vm, S(c, "status", "nodeName"), "spec", "template", "spec", "nodeSelector", "kubernetes.io/hostname")
		return a.Update(vm)
	}
	if S(vm, "spec", "template", "metadata", "annotations", Group+"/shm-channel-uid") != string(c.GetUID()) {
		return invalid("VM bound elsewhere")
	}
	vmi, e := a.Get("vmis", vm.GetName())
	if e != nil {
		return e
	}
	if vmi == nil {
		if S(c, "status", "vmiUID") != "" {
			return a.Status(c, Map{"phase": "Draining", "reason": "VMIEnded"})
		}
		return a.Status(c, Map{"phase": "BackingReady", "reason": "ManualVMStartAllowed"})
	}
	owner := false
	for _, r := range vmi.GetOwnerReferences() {
		if r.UID == vm.GetUID() {
			owner = true
		}
	}
	if !owner {
		return invalid("VMI owner mismatch")
	}
	if uid := S(c, "status", "vmiUID"); uid != "" && uid != string(vmi.GetUID()) {
		return invalid("VMI generation changed")
	}
	if n := S(vmi, "status", "nodeName"); n != "" && n != S(c, "status", "nodeName") {
		return invalid("wrong VMI node")
	}
	if S(c, "status", "vmiUID") == "" {
		return a.Status(c, Map{"phase": "Bound", "vmiUID": string(vmi.GetUID()), "everBound": true})
	}
	if Has([]string{"Succeeded", "Failed"}, S(vmi, "status", "phase")) || vmi.GetDeletionTimestamp() != nil {
		return a.Status(c, Map{"phase": "Draining", "reason": "VMIEnded"})
	}
	w, e := a.Worker(c, p, opts)
	if e != nil {
		return e
	}
	if w == nil {
		return a.Status(c, Map{"phase": "Draining", "reason": "WorkerEnded"})
	}
	for role, uid := range map[string]string{"guest": string(vmi.GetUID()), "worker": string(w.GetUID())} {
		att := Child("attachments", c.GetName()+"-"+role, c)
		Set(att, Map{"channelRef": Ref(c), "generation": S(c, "status", "generation"), "role": role, "holderUID": uid, "nodeName": S(c, "status", "nodeName")}, "spec")
		if _, e = a.Ensure(att, c); e != nil {
			return e
		}
	}
	if Has([]string{"Succeeded", "Failed"}, S(w, "status", "phase")) || w.GetDeletionTimestamp() != nil {
		return a.Status(c, Map{"phase": "Draining", "reason": "WorkerEnded", "workerPodUID": string(w.GetUID())})
	}
	ready := false
	cs, _ := Get(w, "status", "conditions").([]interface{})
	for _, x := range cs {
		m, _ := x.(map[string]interface{})
		if m["type"] == "Ready" && m["status"] == "True" {
			ready = true
		}
	}
	for _, role := range []string{"guest", "worker"} {
		att, e := a.Get("attachments", c.GetName()+"-"+role)
		if e != nil {
			return e
		}
		if att == nil || S(att, "status", "phase") != "Mapped" || N(att, "status", "observedGeneration") != att.GetGeneration() || S(att, "spec", "generation") != S(c, "status", "generation") {
			ready = false
		}
	}
	phase, reason := "Bound", "AwaitingMappingACK"
	if protected && ready {
		phase, reason = "Ready", "MappingACK"
	}
	return a.Status(c, Map{"phase": phase, "reason": reason, "workerPodUID": string(w.GetUID())})
}
func Hook(c *Obj) []interface{} {
	return []interface{}{Map{"image": S(c, "spec", "hookImage"), "args": cmds("--version", "v1alpha2"), "pvc": Map{"name": S(c, "spec", "pvcRef", "name"), "volumePath": "/flyt-channel", "sharedComputePath": "/var/run/flyt-channel"}}}
}
