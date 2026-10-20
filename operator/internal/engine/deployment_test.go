package engine

import (
	"reflect"
	"testing"
)

func TestGeneratedPodsReceiveWorkloadPullSecrets(t *testing.T) {
	c := channel("tenant")
	secrets := []interface{}{Map{"name": "tenant-pull"}}
	p := Pod(c, "prepare-test", "registry.example/helper", cmds("true"),
		Options{Mode: "active", ImagePullSecrets: secrets})
	if !reflect.DeepEqual(Get(p, "spec", "imagePullSecrets"), secrets) {
		t.Fatal("generated Pod lost workload registry credentials")
	}
	if p.GetNamespace() != "tenant" {
		t.Fatal("pull secret must resolve in workload namespace")
	}
}
