package engine

import (
	_ "embed"
	"encoding/json"
	"time"
)

// Bundling the helper with the controller also upgrades existing channels whose
// immutable helper image still points to an older release with Python installed.
//
//go:embed reclaim_helper.py
var reclaimHelper string

func jsonString(v interface{}) string { b, _ := json.Marshal(v); return string(b) }

func reclamationMatches(c *Obj) bool {
	r, ok := Get(c, "status", "reclamation").(map[string]interface{})
	if !ok {
		return false
	}
	var auth struct {
		Identity       Map    `json:"identity"`
		DetachEvidence Map    `json:"detachEvidence"`
		AuthorizedAt   string `json:"authorizedAt"`
	}
	s, _ := r["authorization"].(string)
	if json.Unmarshal([]byte(s), &auth) != nil || !Equal(auth.Identity, completionIdentity(c)) || len(auth.DetachEvidence) != 2 {
		return false
	}
	_, err := time.Parse(time.RFC3339Nano, auth.AuthorizedAt)
	return err == nil && S(c, "status", "reclamation", "journalUID") != "" && S(c, "status", "reclamation", "journalName") == ResourceName(c, "recovery")
}

// Called only after detach checks. No helper is created until a subsequent read
// observes the channel's persisted authorization and the exact journal UID.
func (a API) authorizeReclamation(c *Obj, evidence Map) error {
	if _, err := a.Require("pvcs", Get(c, "spec", "pvcRef")); err != nil {
		return err
	}
	ns, err := a.Get("namespaces", a.Namespace)
	if err != nil {
		return err
	}
	if ns == nil || ns.GetDeletionTimestamp() != nil {
		return WaitError{"NamespaceTerminatingReclaimBlocked"}
	}
	name := ResourceName(c, "recovery")
	cm, err := a.Get("configmaps", name)
	if err != nil {
		return err
	}
	if cm == nil {
		cm = Child("configmaps", name, c)
		auth := Map{"identity": completionIdentity(c), "detachEvidence": evidence, "authorizedAt": time.Now().UTC().Format(time.RFC3339Nano)}
		Set(cm, Map{"authorization": jsonString(auth), "progress": `{"phase":"Authorized"}`}, "data")
		if err := a.Create(cm); err != nil {
			return err
		}
	}
	if !Owned(cm, c) || cm.GetDeletionTimestamp() != nil || string(cm.GetUID()) == "" {
		return WaitError{"ReclamationJournalIdentityUnavailable"}
	}
	var auth struct {
		Identity       Map `json:"identity"`
		DetachEvidence Map `json:"detachEvidence"`
	}
	if json.Unmarshal([]byte(S(cm, "data", "authorization")), &auth) != nil || !Equal(auth.Identity, completionIdentity(c)) || jsonString(auth.DetachEvidence) != jsonString(evidence) {
		return WaitError{"ReclamationAuthorizationMismatch"}
	}
	return a.Status(c, Map{"phase": "Draining", "reason": "ReclamationAuthorized", "reclamation": Map{"journalName": name, "journalUID": string(cm.GetUID()), "authorization": S(cm, "data", "authorization")}})
}

func (a API) resumeReclamation(c *Obj, opts Options) error {
	if !reclamationMatches(c) {
		return WaitError{"ReclamationAuthorizationMismatch"}
	}
	cm, err := a.Get("configmaps", S(c, "status", "reclamation", "journalName"))
	if err != nil {
		return err
	}
	if cm == nil || !Owned(cm, c) || string(cm.GetUID()) != S(c, "status", "reclamation", "journalUID") || cm.GetDeletionTimestamp() != nil || S(cm, "data", "authorization") != S(c, "status", "reclamation", "authorization") {
		return WaitError{"ReclamationJournalIdentityUnavailable"}
	}
	var progress struct {
		Phase string `json:"phase"`
	}
	if json.Unmarshal([]byte(S(cm, "data", "progress")), &progress) != nil || !Has([]string{"Authorized", "Prepared", "Complete"}, progress.Phase) {
		return WaitError{"ReclamationJournalInvalid"}
	}
	if progress.Phase == "Complete" {
		if err := a.releaseDRA(c); err != nil {
			return err
		}
		phase := "Released"
		if persistent(c) && c.GetDeletionTimestamp() == nil && !B(c, "spec", "drain") {
			phase = "Reclaimed"
		}
		return a.recordCompletion(c, phase)
	}
	// Revalidate the volume identity before creating ANY replacement helper.
	if _, err := a.Require("pvcs", Get(c, "spec", "pvcRef")); err != nil {
		return err
	}
	ns, err := a.Get("namespaces", a.Namespace)
	if err != nil {
		return err
	}
	if ns == nil || ns.GetDeletionTimestamp() != nil {
		return WaitError{"NamespaceTerminatingReclaimBlocked"}
	}
	name := ResourceName(c, "recover")
	pod, err := a.Get("pods", name)
	if err != nil {
		return err
	}
	command := cmds("python3", "-c", reclaimHelper, "/flyt-channel", a.Namespace, cm.GetName(), string(cm.GetUID()), S(cm, "data", "authorization"))
	if pod != nil {
		if !Owned(pod, c) || S(pod, "spec", "serviceAccountName") != name {
			return WaitError{"ReclamationHelperIdentityMismatch"}
		}
		containers, _ := Get(pod, "spec", "containers").([]interface{})
		if len(containers) != 1 || !Equal(containers[0].(map[string]interface{})["command"], command) {
			return WaitError{"ReclamationHelperIdentityMismatch"}
		}
		if Has([]string{"Failed", "Succeeded"}, S(pod, "status", "phase")) && pod.GetDeletionTimestamp() == nil {
			// Completion comes from the journal, never from the Pod's exit code.
			return a.Delete(pod)
		}
		return WaitError{"ReclamationPending"}
	}
	sa := Child("serviceaccounts", name, c)
	if _, err = a.Ensure(sa, c); err != nil {
		return err
	}
	role := Child("roles", name, c)
	Set(role, []interface{}{Map{"apiGroups": cmds(""), "resources": cmds("configmaps"), "resourceNames": cmds(cm.GetName()), "verbs": cmds("get", "update")}}, "rules")
	if _, err = a.Ensure(role, c); err != nil {
		return err
	}
	rb := Child("rolebindings", name, c)
	Set(rb, Map{"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": name}, "roleRef")
	Set(rb, []interface{}{Map{"kind": "ServiceAccount", "name": name, "namespace": a.Namespace}}, "subjects")
	if _, err = a.Ensure(rb, c); err != nil {
		return err
	}
	pod = Pod(c, name, S(c, "spec", "image"), command, opts)
	Set(pod, name, "spec", "serviceAccountName")
	Set(pod, true, "spec", "automountServiceAccountToken")
	_, err = a.Ensure(pod, c)
	return err
}

// Keep the completion receipt and channel finalizer until the writer Pod, its
// credentials and the journal are gone. Every delete is UID/RV conditional.
func (a API) cleanupReclamation(c *Obj) error {
	if Get(c, "status", "reclamation") == nil {
		return nil
	} // pre-journal completion
	if !completed(c) || !reclamationMatches(c) {
		return WaitError{"ReclamationCompletionRequired"}
	}
	for _, kind := range []string{"pods", "rolebindings", "roles", "serviceaccounts", "configmaps"} {
		name := ResourceName(c, "recover")
		if kind == "configmaps" {
			name = S(c, "status", "reclamation", "journalName")
		}
		obj, err := a.Get(kind, name)
		if err != nil {
			return err
		}
		if obj == nil {
			continue
		}
		if !Owned(obj, c) || (kind == "configmaps" && string(obj.GetUID()) != S(c, "status", "reclamation", "journalUID")) {
			return WaitError{"ReclamationCleanupIdentityMismatch"}
		}
		if err = a.Delete(obj); err != nil {
			return err
		}
		return WaitError{"ReclamationEvidenceCleanupPending"}
	}
	return nil
}
