package engine

import "testing"

func TestNewWorkerCorePolicy(t *testing.T) {
	for _, policy := range []string{"", "default", "force", "disable"} {
		t.Run(policy, func(t *testing.T) {
			c := channel("a")
			Set(c, "worker-policy", "status", "resourcePrefix")
			Set(c, int64(25), "status", "compute")
			a := fakeAPI("a", c)
			w, err := a.Worker(c, New("profiles"), Options{GPUCorePolicy: policy})
			if err != nil {
				t.Fatal(err)
			}
			container := Get(w, "spec", "containers").([]interface{})[0].(map[string]interface{})
			want := policy
			if want == "" {
				want = "default"
			}
			found := 0
			for _, v := range container["env"].([]interface{}) {
				e := v.(map[string]interface{})
				if e["name"] == "GPU_CORE_UTILIZATION_POLICY" {
					found++
					if e["value"] != want {
						t.Fatal(e)
					}
				}
				if e["name"] == "VMWEAVE_LIVE_COMPUTE" {
					t.Fatal("deferred policy activated")
				}
			}
			if found != 1 {
				t.Fatalf("policy env count %d", found)
			}
			limits := container["resources"].(map[string]interface{})["limits"].(map[string]interface{})
			if limits["nvidia.com/gpucores"] != int64(25) {
				t.Fatal("reservation changed", limits)
			}
		})
	}
}

func TestInvalidWorkerCorePolicyRejected(t *testing.T) {
	c := channel("a")
	a := fakeAPI("a", c)
	if _, err := a.Worker(c, New("profiles"), Options{GPUCorePolicy: "invalid"}); err == nil {
		t.Fatal("invalid policy accepted")
	}
}
