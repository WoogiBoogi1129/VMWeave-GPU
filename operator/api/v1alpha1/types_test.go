package v1alpha1

import (
	"encoding/json"
	"testing"
)

func TestOptionalCompletionIsOmittedFromEmptyTypedStatus(t *testing.T) {
	b, err := json.Marshal(SharedMemoryChannelStatus{})
	if err != nil {
		t.Fatal(err)
	}
	var status map[string]interface{}
	if err = json.Unmarshal(b, &status); err != nil {
		t.Fatal(err)
	}
	if _, ok := status["completion"]; ok {
		t.Fatal("empty typed status emits an invalid completedAt timestamp")
	}
}
func TestCompletionDeepCopyDoesNotAliasReceipt(t *testing.T) {
	original := &SharedMemoryChannel{Status: SharedMemoryChannelStatus{Completion: &SharedMemoryChannelStatusCompletion{Allocation: "original"}}}
	copy := original.DeepCopy()
	copy.Status.Completion.Allocation = "new"
	if original.Status.Completion.Allocation != "original" {
		t.Fatal("completion receipt alias")
	}
}
