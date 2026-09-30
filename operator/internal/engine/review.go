package engine

import (
	"errors"
	"time"
)

func (a API) Review(c *Obj) error {
	accepted, dependencies, reason, message := true, true, "DependenciesPresent", "Declared dependencies present; execution disabled in review mode"
	vm, _, p, pvc, err := a.deps(c)
	if err == nil && S(vm, "spec", "runStrategy") != "Halted" {
		err = invalid("initial VM must be Halted")
	}
	if err == nil {
		err = a.checkPV(pvc, S(p, "spec", "nodeName"))
	}
	if err == nil {
		n, e := a.Get("nodes", S(p, "spec", "nodeName"))
		err = e
		if e == nil && (n == nil || S(n, "status", "allocatable", "nvidia.com/gpu") == "" || S(n, "status", "allocatable", "nvidia.com/gpu") == "0") {
			err = WaitError{"GPUUnavailable"}
		}
	}
	if err != nil {
		var wait WaitError
		var inv InvalidError
		if errors.As(err, &wait) {
			reason = "DependencyNotReady"
		} else if errors.As(err, &inv) {
			accepted = false
			reason = "InvalidConfiguration"
		} else {
			return err
		}
		dependencies = false
		message = err.Error()
	}
	old := map[string]Map{}
	xs, _ := Get(c, "status", "conditions").([]interface{})
	for _, x := range xs {
		m := x.(map[string]interface{})
		t, _ := m["type"].(string)
		old[t] = m
	}
	conds := []interface{}{}
	for _, v := range []struct {
		k    string
		ok   bool
		r, m string
	}{{"Accepted", accepted, reason, message}, {"DependenciesReady", dependencies, reason, message}, {"Ready", false, "ReviewOnly", "Workload execution disabled"}} {
		status := "False"
		if v.ok {
			status = "True"
		}
		ts := time.Now().UTC().Format(time.RFC3339)
		if old[v.k]["status"] == status {
			if t, ok := old[v.k]["lastTransitionTime"].(string); ok {
				ts = t
			}
		}
		conds = append(conds, Map{"type": v.k, "status": status, "reason": v.r, "message": v.m, "observedGeneration": c.GetGeneration(), "lastTransitionTime": ts})
	}
	values := Map{"mode": "review", "observedGeneration": c.GetGeneration(), "conditions": conds}
	if S(c, "status", "allocation") == "" {
		values["phase"] = "ReviewOnly"
	}
	return a.Status(c, values)
}
