package fixture

import "testing"

func TestSample(t *testing.T) {
	if 1+1 != 2 {
		t.Fatal("math is broken")
	}
}
