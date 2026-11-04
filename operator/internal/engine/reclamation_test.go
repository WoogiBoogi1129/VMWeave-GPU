package engine

import (
	"context"
	"errors"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"testing"
	"time"
)

func journalFixture(t *testing.T, mode string) (API, *Obj, *Obj) {
	t.Helper()
	c := channel("a")
	c.SetFinalizers([]string{Finalizer})
	Set(c, mode, "spec", "lifecycle")
	Set(c, Map{"phase": "Draining", "allocation": "11111111111111111111111111111111", "generation": "22222222222222222222222222222222", "everBound": true, "vmiUID": "vmi", "workerPodUID": "worker"}, "status")
	evidence := Map{"guest": "test-detached", "worker": "test-detached"}
	auth := jsonString(Map{"identity": completionIdentity(c), "detachEvidence": evidence, "authorizedAt": time.Now().UTC().Format(time.RFC3339Nano)})
	cm := Child("configmaps", ResourceName(c, "recovery"), c)
	cm.SetUID("journal-uid")
	Set(cm, Map{"authorization": auth, "progress": `{"phase":"Authorized"}`}, "data")
	Set(c, Map{"journalName": cm.GetName(), "journalUID": string(cm.GetUID()), "authorization": auth}, "status", "reclamation")
	pvc := obj("pvcs", "a", "same", "pvc-a")
	ns := obj("namespaces", "", "a", "ns")
	return fakeAPI("a", c, cm, pvc, ns), c, cm
}
func TestReclamationEvidenceIndependentOfPodAndAttachment(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	Set(cm, `{"phase":"Complete"}`, "data", "progress")
	if err := a.Update(cm); err != nil {
		t.Fatal(err)
	}
	// No helper or attachments exist. Only the matching authorized journal is required.
	if err := a.Drain(c, Options{}); err != nil {
		t.Fatal(err)
	}
	fresh, _ := a.Get("channels", c.GetName())
	if !completed(fresh) || S(fresh, "status", "phase") != "Released" {
		t.Fatal(fresh)
	}
	if pods, _ := a.List("pods"); len(pods) != 0 {
		t.Fatal("recreated helper after durable completion")
	}
	for i := 0; i < 10; i++ {
		fresh, _ = a.Get("channels", c.GetName())
		if fresh == nil {
			break
		}
		_ = a.Reconcile(fresh, Options{})
	}
	if fresh, _ = a.Get("channels", c.GetName()); fresh != nil {
		t.Fatal("channel not finalized")
	}
	if journal, _ := a.Get("configmaps", cm.GetName()); journal != nil {
		t.Fatal("journal leaked")
	}
}
func TestReclamationIdentityMismatchAndMissingJournalFailClosed(t *testing.T) {
	for _, scenario := range []string{"missing", "uid", "authorization", "generation", "pvc", "phase"} {
		t.Run(scenario, func(t *testing.T) {
			a, c, cm := journalFixture(t, "Allocation")
			switch scenario {
			case "missing":
				_ = a.Delete(cm)
			case "uid":
				cm.SetUID("replacement")
				_ = a.Update(cm)
			case "authorization":
				Set(cm, "{}", "data", "authorization")
				_ = a.Update(cm)
			case "generation":
				Set(c, "different", "status", "generation")
			case "pvc":
				Set(c, "different", "spec", "pvcRef", "uid")
			case "phase":
				Set(cm, `{"phase":"Unknown"}`, "data", "progress")
				_ = a.Update(cm)
			}
			if err := a.resumeReclamation(c, Options{}); err == nil {
				t.Fatal("invalid evidence accepted")
			}
			if pods, _ := a.List("pods"); len(pods) != 0 {
				t.Fatal("helper created without evidence")
			}
		})
	}
}
func TestReclamationHelperUsesOnlyNamedJournalAndEmbeddedCode(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	if err := a.resumeReclamation(c, Options{}); err != nil {
		t.Fatal(err)
	}
	pod, _ := a.Get("pods", ResourceName(c, "recover"))
	if pod == nil {
		t.Fatal("helper absent")
	}
	role, _ := a.Get("roles", pod.GetName())
	want := []interface{}{Map{"apiGroups": cmds(""), "resources": cmds("configmaps"), "resourceNames": cmds(cm.GetName()), "verbs": cmds("get", "update")}}
	if !Equal(Get(role, "rules"), want) {
		t.Fatal("helper privileges exceed named journal")
	}
	containers := Get(pod, "spec", "containers").([]interface{})
	command := containers[0].(map[string]interface{})["command"].([]interface{})
	if command[2] != reclaimHelper {
		t.Fatal("old image script used")
	}
	if err := a.Status(pod, Map{"phase": "Failed"}); err != nil {
		t.Fatal(err)
	}
	if err := a.resumeReclamation(c, Options{}); err != nil {
		t.Fatal(err)
	}
	if err := a.resumeReclamation(c, Options{}); err != nil {
		t.Fatal(err)
	}
	if pod, _ = a.Get("pods", ResourceName(c, "recover")); pod == nil {
		t.Fatal("failed helper not retried")
	}
	if err := a.Status(pod, Map{"phase": "Succeeded"}); err != nil {
		t.Fatal(err)
	}
	_ = a.resumeReclamation(c, Options{})
	fresh, _ := a.Get("channels", c.GetName())
	if completed(fresh) {
		t.Fatal("Pod success treated as completion")
	}
}
func TestReclamationDRAWaitsBeforeCompletion(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	// Rebind fixture identity before storing the authorization.
	Set(c, "hami-dra", "status", "backend")
	Set(c, "claim", "status", "claimUID")
	Set(c, ResourceName(c, "gpu"), "status", "claimName")
	auth := jsonString(Map{"identity": completionIdentity(c), "detachEvidence": Map{"guest": "detached", "worker": "detached"}, "authorizedAt": time.Now().UTC().Format(time.RFC3339Nano)})
	_ = a.Status(c, Map{"reclamation": Map{"journalName": cm.GetName(), "journalUID": string(cm.GetUID()), "authorization": auth}})
	Set(cm, auth, "data", "authorization")
	Set(cm, `{"phase":"Complete"}`, "data", "progress")
	_ = a.Update(cm)
	claim := Child("claims", ResourceName(c, "gpu"), c)
	claim.SetUID("claim")
	claim.SetAnnotations(map[string]string{Group + "/allocation": S(c, "status", "allocation")})
	claim.SetFinalizers([]string{"test/hold"})
	_ = a.Create(claim)
	if err := a.resumeReclamation(c, Options{}); err == nil {
		t.Fatal("pending DRA accepted")
	}
	fresh, _ := a.Get("channels", c.GetName())
	if completed(fresh) {
		t.Fatal("completion before claim release")
	}
	claim, _ = a.Get("claims", claim.GetName())
	claim.SetFinalizers(nil)
	_ = a.Update(claim)
	if err := a.resumeReclamation(c, Options{}); err != nil {
		t.Fatal(err)
	}
}
func TestPersistentReclamationCleansJournalBeforeReset(t *testing.T) {
	a, c, cm := journalFixture(t, "VM")
	Set(cm, `{"phase":"Complete"}`, "data", "progress")
	_ = a.Update(cm)
	if err := a.resumeReclamation(c, Options{}); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 10; i++ {
		fresh, _ := a.Get("channels", c.GetName())
		if err := a.FinishStop(fresh); err != nil {
			var w WaitError
			if !errors.As(err, &w) {
				t.Fatal(err)
			}
		}
	}
	fresh, _ := a.Get("channels", c.GetName())
	if S(fresh, "status", "phase") != "Stopped" || Get(fresh, "status", "completion") != nil || Get(fresh, "status", "reclamation") != nil || S(fresh, "status", "allocation") != "" {
		t.Fatal(fresh)
	}
	if journal, _ := a.Get("configmaps", cm.GetName()); journal != nil {
		t.Fatal("journal leaked across boots")
	}
}

type failingStatusClient struct {
	client.Client
	fail bool
}
type failingStatusWriter struct {
	client.SubResourceWriter
	parent *failingStatusClient
}

func (c *failingStatusClient) Status() client.SubResourceWriter {
	return &failingStatusWriter{c.Client.Status(), c}
}
func (w *failingStatusWriter) Update(ctx context.Context, obj client.Object, opts ...client.SubResourceUpdateOption) error {
	if w.parent.fail {
		return errors.New("injected API status failure")
	}
	return w.SubResourceWriter.Update(ctx, obj, opts...)
}
func TestCompletionWriteFailureRetainsJournalAndRetries(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	Set(cm, `{"phase":"Complete"}`, "data", "progress")
	_ = a.Update(cm)
	f := &failingStatusClient{a.C, true}
	a.C = f
	if err := a.resumeReclamation(c, Options{}); err == nil {
		t.Fatal("fault not injected")
	}
	fresh, _ := a.Get("channels", c.GetName())
	if completed(fresh) {
		t.Fatal("failed API write claimed completion")
	}
	if journal, _ := a.Get("configmaps", cm.GetName()); journal == nil {
		t.Fatal("journal lost before completion")
	}
	f.fail = false
	if err := a.resumeReclamation(fresh, Options{}); err != nil {
		t.Fatal(err)
	}
	fresh, _ = a.Get("channels", c.GetName())
	if !completed(fresh) {
		t.Fatal("did not recover")
	}
}
func TestAuthorizationIsSavedBeforeHelperCreation(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	_ = a.Status(c, Map{"reclamation": nil})
	evidence := Map{"guest": "test-detached", "worker": "test-detached"}
	if err := a.authorizeReclamation(c, evidence); err != nil {
		t.Fatal(err)
	}
	fresh, _ := a.Get("channels", c.GetName())
	if !reclamationMatches(fresh) || S(fresh, "status", "reclamation", "journalUID") != string(cm.GetUID()) {
		t.Fatal("authorization not persisted")
	}
	if pods, _ := a.List("pods"); len(pods) != 0 {
		t.Fatal("helper launched in same unconfirmed status write")
	}
}

func TestCleanupFailureHoldsCompletionAndFinalizer(t *testing.T) {
	a, c, cm := journalFixture(t, "Allocation")
	if err := a.recordCompletion(c, "Released"); err != nil {
		t.Fatal(err)
	}
	cm.SetFinalizers([]string{"test/hold"})
	if err := a.Update(cm); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		fresh, _ := a.Get("channels", c.GetName())
		if err := a.Reconcile(fresh, Options{}); err == nil {
			t.Fatal("finalized before journal deletion")
		}
		fresh, _ = a.Get("channels", c.GetName())
		if !completed(fresh) || !Has(fresh.GetFinalizers(), Finalizer) {
			t.Fatal("lost receipt/finalizer")
		}
	}
	cm, _ = a.Get("configmaps", cm.GetName())
	cm.SetFinalizers(nil)
	_ = a.Update(cm)
	for i := 0; i < 3; i++ {
		fresh, _ := a.Get("channels", c.GetName())
		if fresh == nil {
			break
		}
		if err := a.Reconcile(fresh, Options{}); err != nil {
			t.Fatal(err)
		}
	}
	if fresh, _ := a.Get("channels", c.GetName()); fresh != nil {
		t.Fatal("could not resume after journal deletion")
	}
}
func TestDetachMustBelongToExactRuntimeBeforeAuthorization(t *testing.T) {
	for _, field := range []string{"holderUID", "role", "nodeName", "generation"} {
		t.Run(field, func(t *testing.T) {
			a, c, cm := journalFixture(t, "Allocation")
			_ = a.Delete(cm)
			_ = a.Status(c, Map{"reclamation": nil})
			for _, role := range []string{"guest", "worker"} {
				att := Child("attachments", c.GetName()+"-"+role, c)
				att.SetGeneration(1)
				att.SetUID("att-" + types.UID(role))
				holder := "vmi"
				if role == "worker" {
					holder = "worker"
				}
				Set(att, Map{"channelRef": Ref(c), "generation": S(c, "status", "generation"), "role": role, "holderUID": holder, "nodeName": ""}, "spec")
				Set(att, Map{"phase": "Detached", "observedGeneration": int64(1)}, "status")
				if role == "worker" {
					Set(att, "foreign", "spec", field)
				}
				_ = a.Create(att)
			}
			if err := a.Drain(c, Options{}); err != nil {
				t.Fatal(err)
			}
			fresh, _ := a.Get("channels", c.GetName())
			if S(fresh, "status", "reason") != "AwaitingDetachEvidence" || Get(fresh, "status", "reclamation") != nil {
				t.Fatal("stale detach authorized")
			}
			if cm, _ := a.Get("configmaps", ResourceName(c, "recovery")); cm != nil {
				t.Fatal("journal created from stale evidence")
			}
		})
	}
}
