package engine

import (
	"fmt"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

func Terminal(p *Obj) bool {
	var pod corev1.Pod
	if runtime.DefaultUnstructuredConverter.FromUnstructured(p.Object, &pod) != nil {
		return false
	}
	if pod.Status.Phase != corev1.PodSucceeded && pod.Status.Phase != corev1.PodFailed {
		return false
	}
	if len(pod.Spec.Containers) == 0 {
		return false
	}
	check := func(names []string, ss []corev1.ContainerStatus) bool {
		if len(names) != len(ss) {
			return false
		}
		seen := map[string]bool{}
		for _, s := range ss {
			if s.State.Terminated == nil || seen[s.Name] {
				return false
			}
			seen[s.Name] = true
		}
		for _, n := range names {
			if !seen[n] {
				return false
			}
		}
		return true
	}
	names := func(cs []corev1.Container) []string {
		r := []string{}
		for _, c := range cs {
			r = append(r, c.Name)
		}
		return r
	}
	es := []string{}
	for _, c := range pod.Spec.EphemeralContainers {
		es = append(es, c.Name)
	}
	return check(names(pod.Spec.Containers), pod.Status.ContainerStatuses) && check(names(pod.Spec.InitContainers), pod.Status.InitContainerStatuses) && check(es, pod.Status.EphemeralContainerStatuses)
}
func TerminalUnstarted(p *Obj) bool {
	var pod corev1.Pod
	if runtime.DefaultUnstructuredConverter.FromUnstructured(p.Object, &pod) != nil {
		return false
	}
	if pod.Status.Phase != corev1.PodFailed || pod.DeletionTimestamp == nil || len(pod.Spec.EphemeralContainers) > 0 || len(pod.Status.EphemeralContainerStatuses) > 0 {
		return false
	}
	initFalse, sandbox := false, false
	for _, c := range pod.Status.Conditions {
		if c.Type == corev1.PodInitialized && c.Status == corev1.ConditionFalse {
			initFalse = true
		}
		if string(c.Type) == "PodReadyToStartContainers" && c.Status == corev1.ConditionFalse && c.Reason == "PodSandboxNotReady" {
			sandbox = true
		}
	}
	if !initFalse || !sandbox || len(pod.Spec.Containers) == 0 {
		return false
	}
	unstarted := func(s corev1.ContainerStatus) bool {
		return s.State.Waiting != nil && s.State.Waiting.Reason == "PodInitializing" && s.State.Running == nil && s.State.Terminated == nil && s.ContainerID == "" && s.ImageID == "" && s.RestartCount == 0 && !s.Ready && s.Started != nil && !*s.Started && s.LastTerminationState.Terminated == nil && s.LastTerminationState.Running == nil && s.LastTerminationState.Waiting == nil
	}
	if len(pod.Spec.Containers) != len(pod.Status.ContainerStatuses) || len(pod.Spec.InitContainers) != len(pod.Status.InitContainerStatuses) {
		return false
	}
	seen := map[string]bool{}
	for _, s := range pod.Status.ContainerStatuses {
		if !unstarted(s) || seen[s.Name] {
			return false
		}
		seen[s.Name] = true
	}
	for _, c := range pod.Spec.Containers {
		if !seen[c.Name] {
			return false
		}
	}
	regular := map[string]bool{}
	for _, c := range pod.Spec.InitContainers {
		regular[c.Name] = c.RestartPolicy == nil || *c.RestartPolicy != corev1.ContainerRestartPolicyAlways
	}
	barrier := false
	seen = map[string]bool{}
	for _, s := range pod.Status.InitContainerStatuses {
		r, ok := regular[s.Name]
		if !ok || seen[s.Name] {
			return false
		}
		seen[s.Name] = true
		if r && unstarted(s) {
			barrier = true
		}
		if s.State.Terminated == nil && !unstarted(s) {
			return false
		}
	}
	return barrier
}
func (a API) nodeReady(n string) (bool, error) {
	o, e := a.Get("nodes", n)
	if e != nil || o == nil {
		return false, e
	}
	cs, _ := Get(o, "status", "conditions").([]interface{})
	for _, v := range cs {
		m, _ := v.(map[string]interface{})
		if m["type"] == "Ready" && m["status"] == "True" {
			return true, nil
		}
	}
	return false, nil
}
func (a API) protect(p, c *Obj) (bool, error) {
	owner := p.GetAnnotations()[DetachChannel]
	if owner != "" && owner != string(c.GetUID()) {
		return false, invalid("foreign detach observer")
	}
	if Has(p.GetFinalizers(), DetachFinalizer) {
		if owner != string(c.GetUID()) {
			return false, invalid("unowned detach finalizer")
		}
		return true, nil
	}
	if p.GetDeletionTimestamp() != nil {
		return false, nil
	}
	an := p.GetAnnotations()
	if an == nil {
		an = map[string]string{}
	}
	an[DetachChannel] = string(c.GetUID())
	p.SetAnnotations(an)
	p.SetFinalizers(append(p.GetFinalizers(), DetachFinalizer))
	return true, a.Update(p)
}
func (a API) release(p, c *Obj) error {
	if !Has(p.GetFinalizers(), DetachFinalizer) {
		return nil
	}
	if p.GetAnnotations()[DetachChannel] != string(c.GetUID()) {
		return invalid("foreign detach observer")
	}
	p.SetFinalizers(Remove(p.GetFinalizers(), DetachFinalizer))
	return a.Update(p)
}
func (a API) Observe(c *Obj) (bool, error) {
	guestProtected := false
	for _, role := range []string{"guest", "worker"} {
		att, e := a.Get("attachments", c.GetName()+"-"+role)
		if e != nil {
			return false, e
		}
		if att == nil || !Equal(Get(att, "spec", "channelRef"), Ref(c)) || S(att, "spec", "generation") != S(c, "status", "generation") {
			continue
		}
		var p *Obj
		if role == "worker" {
			p, e = a.Get("pods", ResourceName(c, "worker"))
			if e != nil {
				return false, e
			}
			if p != nil && string(p.GetUID()) != S(att, "spec", "holderUID") {
				p = nil
			}
		} else {
			ps, err := a.List("pods")
			if err != nil {
				return false, err
			}
			matches := []Obj{}
			for _, x := range ps {
				if x.GetLabels()["kubevirt.io/created-by"] == S(att, "spec", "holderUID") && (S(att, "status", "launcherPodUID") == "" || S(att, "status", "launcherPodUID") == string(x.GetUID())) {
					matches = append(matches, x)
				}
			}
			if len(matches) == 1 {
				p = matches[0].DeepCopy()
			}
		}
		if p == nil || S(p, "spec", "nodeName") != S(att, "spec", "nodeName") {
			continue
		}
		if S(att, "status", "phase") == "Detached" {
			if e = a.release(p, c); e != nil {
				return false, e
			}
			continue
		}
		protected, err := a.protect(p, c)
		if err != nil {
			return false, err
		}
		if role == "guest" {
			guestProtected = protected
			if S(att, "status", "launcherPodUID") == "" {
				if err = a.Status(att, Map{"launcherPodUID": string(p.GetUID())}); err != nil {
					return false, err
				}
				continue
			}
		}
		unstarted := role == "guest" && S(att, "status", "phase") == "" && TerminalUnstarted(p)
		if !Terminal(p) && !unstarted {
			continue
		}
		ready, err := a.nodeReady(S(att, "spec", "nodeName"))
		if err != nil {
			return false, err
		}
		if !ready {
			continue
		}
		v := Map{"phase": "Detached", "observedGeneration": att.GetGeneration()}
		if role == "worker" {
			v["reporterPodUID"] = string(p.GetUID())
			v["evidence"] = "KubeletTerminalWorker"
		} else {
			v["launcherPodUID"] = string(p.GetUID())
			v["evidence"] = "KubeletTerminalLauncher"
			if unstarted {
				v["evidence"] = "KubeletTerminalUnstartedLauncher"
			}
		}
		if err = a.Status(att, v); err != nil {
			return false, err
		}
		if err = a.release(p, c); err != nil {
			return false, fmt.Errorf("release observation: %w", err)
		}
		if role == "guest" {
			guestProtected = false
		}
	}
	return guestProtected, nil
}
