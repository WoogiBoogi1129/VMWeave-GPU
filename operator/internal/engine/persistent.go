package engine

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"strings"
)

func persistent(c *Obj) bool { return S(c, "spec", "lifecycle") == "VM" }
func podReady(p *Obj) bool {
	cs, _ := Get(p, "status", "conditions").([]interface{})
	for _, v := range cs {
		m, _ := v.(map[string]interface{})
		if m["type"] == "Ready" && m["status"] == "True" {
			return true
		}
	}
	return false
}

// The VM owns the durable binding, while each boot owns a fresh allocation.
func (a API) PersistentPrelude(c *Obj) (bool, error) {
	vm, e := a.Get("vms", S(c, "spec", "vmRef", "name"))
	if e != nil {
		return true, e
	}
	if S(c, "status", "phase") == "Reclaimed" {
		return true, a.FinishStop(c)
	}
	if c.GetDeletionTimestamp() != nil || B(c, "spec", "drain") {
		return false, nil
	}
	if vm == nil || string(vm.GetUID()) != S(c, "spec", "vmRef", "uid") || vm.GetDeletionTimestamp() != nil {
		return true, a.Delete(c)
	}
	if !Owned(c, vm) {
		yes := true
		c.SetOwnerReferences([]metav1.OwnerReference{{APIVersion: "kubevirt.io/v1", Kind: "VirtualMachine", Name: vm.GetName(), UID: vm.GetUID(), Controller: &yes}})
		return true, a.Update(c)
	}
	phase := S(c, "status", "phase")
	if phase == "" && S(c, "status", "allocation") == "" && S(vm, "spec", "runStrategy") == "Halted" {
		return true, a.Status(c, Map{"phase": "Stopped", "reason": "AwaitingVMStart"})
	}
	if phase == "Stopped" {
		if S(vm, "spec", "runStrategy") == "Halted" {
			return true, nil
		}
		if S(vm, "spec", "runStrategy") != "Always" {
			return true, WaitError{"persistent VM requires Always/Halted runStrategy"}
		}
		return false, nil
	}
	// A previous runtime must finish detaching before a new VMI can be admitted.
	if phase == "Draining" || phase == "Failed" {
		return false, nil
	}
	vmi, e := a.Get("vmis", vm.GetName())
	if e != nil {
		return true, e
	}
	if S(c, "status", "allocation") != "" && S(vm, "spec", "runStrategy") == "Halted" {
		return true, a.Status(c, Map{"phase": "Draining", "reason": "VMStopped"})
	}
	if S(c, "status", "vmiUID") != "" && (vmi == nil || string(vmi.GetUID()) != S(c, "status", "vmiUID") || vmi.GetDeletionTimestamp() != nil || Has([]string{"Succeeded", "Failed"}, S(vmi, "status", "phase"))) {
		return true, a.Status(c, Map{"phase": "Draining", "reason": "VMIEnded"})
	}
	return false, nil
}

// Called only after durable detach evidence and successful backing reclamation.
func (a API) FinishStop(c *Obj) error {
	for _, kind := range []string{"attachments", "pods", "rolebindings", "roles", "serviceaccounts"} {
		xs, e := a.List(kind)
		if e != nil {
			return e
		}
		for _, x := range xs {
			if Owned(&x, c) {
				if e = a.Delete(&x); e != nil {
					return e
				}
				return nil
			}
		}
	}
	return a.Status(c, Map{"phase": "Stopped", "reason": "RuntimeReclaimed", "allocation": "", "generation": "", "resourcePrefix": "", "vmiUID": "", "workerPodUID": "", "everBound": false, "sessions": []interface{}{}})
}

// Match provision.py's little-endian layout. cloud-init comments are available
// from each boot's config drive even when cloud-init does not rerun user-data.
func installBootLayout(vm, c *Obj) error {
	ss, _ := Get(c, "status", "sessions").([]interface{})
	if len(ss) == 0 || len(ss) > 32 {
		return invalid("invalid layout sessions")
	}
	var slots bytes.Buffer
	pos := uint64(4096)
	for _, id := range ss {
		sid, e := hex.DecodeString(id.(string))
		if e != nil || len(sid) != 16 {
			return invalid("invalid session ID")
		}
		slots.Write(sid)
		for j := 0; j < 2; j++ {
			binary.Write(&slots, binary.LittleEndian, pos)
			binary.Write(&slots, binary.LittleEndian, uint32(64))
			binary.Write(&slots, binary.LittleEndian, uint32(0))
			pos += 128 + 64*128
		}
		for j := 0; j < 2; j++ {
			binary.Write(&slots, binary.LittleEndian, pos)
			binary.Write(&slots, binary.LittleEndian, uint64(17*1024*1024))
			pos += 17 * 1024 * 1024
		}
	}
	var b bytes.Buffer
	for _, key := range []string{"allocation", "generation"} {
		id, e := hex.DecodeString(S(c, "status", key))
		if e != nil || len(id) != 16 {
			return invalid("invalid runtime ID")
		}
		b.Write(id)
	}
	size := uint64(4096)
	for size < pos {
		size *= 2
	}
	binary.Write(&b, binary.LittleEndian, size)
	binary.Write(&b, binary.LittleEndian, uint32(len(ss)))
	b.Write(make([]byte, 20))
	b.Write(slots.Bytes())
	const marker = "# vmweave-layout-b64: "
	volumes, _ := Get(vm, "spec", "template", "spec", "volumes").([]interface{})
	for _, v := range volumes {
		volume, _ := v.(map[string]interface{})
		config, ok := volume["cloudInitNoCloud"].(map[string]interface{})
		if !ok {
			continue
		}
		data, ok := config["userData"].(string)
		if !ok {
			return invalid("persistent VM requires inline cloudInitNoCloud userData")
		}
		lines := []string{}
		for _, line := range strings.Split(data, "\n") {
			if !strings.HasPrefix(line, marker) {
				lines = append(lines, line)
			}
		}
		config["userData"] = strings.TrimRight(strings.Join(lines, "\n"), "\n") + "\n" + marker + base64.StdEncoding.EncodeToString(b.Bytes()) + "\n"
		Set(vm, volumes, "spec", "template", "spec", "volumes")
		return nil
	}
	return invalid("persistent VM requires cloudInitNoCloud volume")
}
