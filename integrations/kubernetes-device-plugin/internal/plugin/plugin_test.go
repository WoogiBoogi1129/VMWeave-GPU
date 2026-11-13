package plugin

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"google.golang.org/grpc"
	api "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fixture(t *testing.T) (Config, Discovery) {
	t.Helper()
	dir := t.TempDir()
	broker := filepath.Join(dir, "broker")
	state := filepath.Join(dir, "state")
	for _, p := range []string{broker, state} {
		if e := os.Mkdir(p, 0755); e != nil {
			t.Fatal(e)
		}
	}
	l, e := net.Listen("unix", filepath.Join(broker, "gpu.sock"))
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { l.Close() })
	if e = os.Chmod(filepath.Join(broker, "gpu.sock"), 0660); e != nil {
		t.Fatal(e)
	}
	c := Config{PluginDir: dir, StatusFile: filepath.Join(state, "status.json"), BrokerDir: broker, LibrarySHA256: strings.Repeat("a", 64), BrokerGID: os.Getgid(), OwnerUID: uint32(os.Getuid()), BootID: "test-boot", MaxAge: 10 * time.Second, Poll: 20 * time.Millisecond}
	d := Discovery{SchemaVersion: 1, BrokerProtocol: 1, Allocation: strings.Repeat("1", 32), Generation: strings.Repeat("2", 32), BootID: c.BootID, LibrarySHA256: c.LibrarySHA256, MaxClients: 1, Ready: true, ObservedAt: float64(time.Now().Unix()), TransportObservedAt: float64(time.Now().Unix())}
	write(t, c, d)
	return c, d
}
func write(t *testing.T, c Config, d Discovery) {
	t.Helper()
	b, _ := json.Marshal(d)
	tmp := c.StatusFile + ".tmp"
	if e := os.WriteFile(tmp, b, 0644); e != nil {
		t.Fatal(e)
	}
	if e := os.Rename(tmp, c.StatusFile); e != nil {
		t.Fatal(e)
	}
}
func TestHealthAndAllocation(t *testing.T) {
	c, d := fixture(t)
	s := &Server{Config: c}
	req := &api.AllocateRequest{ContainerRequests: []*api.ContainerAllocateRequest{{DevicesIds: []string{DeviceID}}}}
	for _, busy := range []bool{false, true} {
		d.ActiveClient = busy
		write(t, c, d)
		r, e := s.Allocate(context.Background(), req)
		if e != nil {
			t.Fatal(e)
		}
		cr := r.ContainerResponses[0]
		if len(cr.Devices) != 0 || len(cr.Mounts) != 1 || !cr.Mounts[0].ReadOnly || cr.Envs["VMWEAVE_BROKER_SOCKET"] != "/run/vmweave/gpu.sock" {
			t.Fatalf("unsafe injection: %+v", cr)
		}
	}
	// Repeated Allocate returns the same connection config; it opens no session.
	for _, r := range []*api.AllocateRequest{nil, {}, {ContainerRequests: []*api.ContainerAllocateRequest{nil}}, {ContainerRequests: []*api.ContainerAllocateRequest{{DevicesIds: []string{"unknown"}}}}, {ContainerRequests: []*api.ContainerAllocateRequest{{DevicesIds: []string{DeviceID, DeviceID}}}}, {ContainerRequests: []*api.ContainerAllocateRequest{req.ContainerRequests[0], req.ContainerRequests[0]}}} {
		if _, e := s.Allocate(context.Background(), r); e == nil {
			t.Fatal("accepted invalid allocation")
		}
	}
	cases := map[string]func(*Discovery){"stale": func(x *Discovery) { x.ObservedAt -= 20 }, "stalled": func(x *Discovery) { x.TransportObservedAt -= 20 }, "future": func(x *Discovery) { x.ObservedAt += 60 }, "abi": func(x *Discovery) { x.BrokerProtocol = 2 }, "library": func(x *Discovery) { x.LibrarySHA256 = strings.Repeat("b", 64) }, "boot": func(x *Discovery) { x.BootID = "previous" }, "failed": func(x *Discovery) { x.Ready = false }, "identity": func(x *Discovery) { x.Generation = strings.Repeat("0", 32) }, "slots": func(x *Discovery) { x.MaxClients = 2 }}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			bad := d
			mutate(&bad)
			write(t, c, bad)
			if _, e := s.Allocate(context.Background(), req); e == nil {
				t.Fatal("unhealthy allocation accepted")
			}
		})
	}
}
func TestUntrustedFiles(t *testing.T) {
	for _, scenario := range []string{"symlink", "writable", "directory", "gid", "socket", "malformed", "trailing"} {
		t.Run(scenario, func(t *testing.T) {
			c, _ := fixture(t)
			switch scenario {
			case "symlink":
				os.Rename(c.StatusFile, c.StatusFile+".real")
				os.Symlink(c.StatusFile+".real", c.StatusFile)
			case "writable":
				os.Chmod(c.StatusFile, 0666)
			case "directory":
				os.Chmod(filepath.Dir(c.StatusFile), 0777)
			case "gid":
				c.BrokerGID++
			case "socket":
				os.Remove(filepath.Join(c.BrokerDir, "gpu.sock"))
				os.WriteFile(filepath.Join(c.BrokerDir, "gpu.sock"), nil, 0660)
			case "malformed":
				os.WriteFile(c.StatusFile, []byte("{"), 0644)
			case "trailing":
				f, _ := os.OpenFile(c.StatusFile, os.O_APPEND|os.O_WRONLY, 0)
				f.WriteString("{}")
				f.Close()
			}
			if _, e := c.Check(time.Now()); e == nil {
				t.Fatal("untrusted input accepted")
			}
		})
	}
}

type registrar struct {
	api.UnimplementedRegistrationServer
	requests chan *api.RegisterRequest
}

func (r *registrar) Register(_ context.Context, q *api.RegisterRequest) (*api.Empty, error) {
	r.requests <- q
	return &api.Empty{}, nil
}
func fakeKubelet(t *testing.T, c Config) (*grpc.Server, *registrar) {
	t.Helper()
	l, e := net.Listen("unix", filepath.Join(c.PluginDir, "kubelet.sock"))
	if e != nil {
		t.Fatal(e)
	}
	l.(*net.UnixListener).SetUnlinkOnClose(false)
	g := grpc.NewServer()
	r := &registrar{requests: make(chan *api.RegisterRequest, 8)}
	api.RegisterRegistrationServer(g, r)
	go g.Serve(l)
	t.Cleanup(func() { g.Stop(); l.Close() })
	return g, r
}
func registration(t *testing.T, r *registrar) {
	t.Helper()
	select {
	case q := <-r.requests:
		if q.ResourceName != Resource || q.Endpoint != "vmweave.sock" || q.Version != api.Version {
			t.Fatal(q)
		}
	case <-time.After(8 * time.Second):
		t.Fatal("registration timeout")
	}
}
func TestKubeletLifecycle(t *testing.T) {
	c, d := fixture(t)
	// Production runs as root with a nonzero group. Tests may run under root in CI.
	if c.BrokerGID == 0 {
		c.BrokerGID = 1000
		if e := os.Chown(filepath.Join(c.BrokerDir, "gpu.sock"), 0, 1000); e != nil {
			t.Fatal(e)
		}
	}
	g, r := fakeKubelet(t, c)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- Run(ctx, c, t.Logf) }()
	registration(t, r)
	dc, stop := context.WithTimeout(ctx, 4*time.Second)
	defer stop()
	conn, e := Dial(dc, filepath.Join(c.PluginDir, "vmweave.sock"))
	if e != nil {
		t.Fatal(e)
	}
	defer conn.Close()
	client := api.NewDevicePluginClient(conn)
	stream, e := client.ListAndWatch(dc, &api.Empty{})
	if e != nil {
		t.Fatal(e)
	}
	first, e := stream.Recv()
	if e != nil || first.Devices[0].Health != api.Healthy {
		t.Fatalf("initial health %v %v", first, e)
	}
	d.Ready = false
	write(t, c, d)
	next, e := stream.Recv()
	if e != nil || next.Devices[0].Health != api.Unhealthy {
		t.Fatalf("failed transition %v %v", next, e)
	}
	d.Ready = true
	write(t, c, d)
	next, e = stream.Recv()
	if e != nil || next.Devices[0].Health != api.Healthy {
		t.Fatal("recovery missing", e)
	}
	if e := Run(ctx, c, t.Logf); e == nil {
		t.Fatal("duplicate instance accepted")
	}
	g.Stop()
	os.Remove(filepath.Join(c.PluginDir, "kubelet.sock"))
	os.Remove(filepath.Join(c.PluginDir, "vmweave.sock"))
	_, r2 := fakeKubelet(t, c)
	registration(t, r2)
	cancel()
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("shutdown timeout")
	}
}

func multiFixture(t *testing.T) (Config, []Discovery) {
	c, d := fixture(t)
	c.SlotCount = 2
	layout := make([]byte, 224)
	copy(layout[:16], bytes.Repeat([]byte{0x11}, 16))
	copy(layout[16:32], bytes.Repeat([]byte{0x22}, 16))
	binary.LittleEndian.PutUint32(layout[40:44], 2)
	records := []Discovery{}
	for slot := 0; slot < 2; slot++ {
		copy(layout[64+80*slot:80+80*slot], bytes.Repeat([]byte{byte(0x33 + slot)}, 16))
		dir := c.brokerPath(slot)
		state := filepath.Join(filepath.Dir(c.StatusFile), "slots", fmt.Sprint(slot))
		if e := os.MkdirAll(dir, 0755); e != nil {
			t.Fatal(e)
		}
		if e := os.MkdirAll(state, 0755); e != nil {
			t.Fatal(e)
		}
		l, e := net.Listen("unix", filepath.Join(dir, "gpu.sock"))
		if e != nil {
			t.Fatal(e)
		}
		t.Cleanup(func() { l.Close() })
		os.Chmod(filepath.Join(dir, "gpu.sock"), 0660)
		x := d
		x.SchemaVersion = 2
		x.SlotCount = 2
		i := slot
		x.SlotIndex = &i
		x.SessionID = hex.EncodeToString(layout[64+80*slot : 80+80*slot])
		records = append(records, x)
		sc := c
		sc.StatusFile = filepath.Join(state, "status.json")
		write(t, sc, x)
	}
	if e := os.WriteFile(filepath.Join(c.BrokerDir, "layout.bin"), layout, 0644); e != nil {
		t.Fatal(e)
	}
	return c, records
}
func TestFixedSlotsBindingAndMounts(t *testing.T) {
	c, records := multiFixture(t)
	s := &Server{Config: c}
	request := &api.AllocateRequest{ContainerRequests: []*api.ContainerAllocateRequest{{DevicesIds: []string{"vmweave-slot-0"}}, {DevicesIds: []string{"vmweave-slot-1"}}}}
	for i := 0; i < 2; i++ {
		r, e := s.Allocate(context.Background(), request)
		if e != nil {
			t.Fatal(e)
		}
		for slot, cr := range r.ContainerResponses {
			if cr.Mounts[0].HostPath != c.brokerPath(slot) || len(cr.Devices) != 0 {
				t.Fatal(cr)
			}
		}
	}
	sc := c
	sc.StatusFile = filepath.Join(filepath.Dir(c.StatusFile), "slots", "1", "status.json")
	for name, mutate := range map[string]func(*Discovery){
		"wrong-slot": func(d *Discovery) { i := 0; d.SlotIndex = &i }, "missing-slot": func(d *Discovery) { d.SlotIndex = nil },
		"generation": func(d *Discovery) { d.Generation = strings.Repeat("a", 32) }, "session": func(d *Discovery) { d.SessionID = records[0].SessionID },
		"count": func(d *Discovery) { d.SlotCount = 1 }, "stalled": func(d *Discovery) { d.TransportObservedAt -= 20 },
	} {
		t.Run(name, func(t *testing.T) {
			bad := records[1]
			mutate(&bad)
			write(t, sc, bad)
			if _, e := c.CheckSlot(time.Now(), 1); e == nil {
				t.Fatal("accepted bad slot")
			}
			if _, e := c.CheckSlot(time.Now(), 0); e != nil {
				t.Fatal("peer failed", e)
			}
			if _, e := s.Allocate(context.Background(), request); e == nil {
				t.Fatal("allocated failed slot")
			}
		})
	}
	write(t, sc, records[1])
	os.Remove(sc.StatusFile)
	if _, e := c.CheckSlot(time.Now(), 1); e == nil {
		t.Fatal("missing status accepted")
	}
	if _, e := c.CheckSlot(time.Now(), 0); e != nil {
		t.Fatal(e)
	}
}
func TestLayoutAndPathFencing(t *testing.T) {
	for _, scenario := range []string{"count", "duplicate", "layout-symlink", "directory-symlink", "writable"} {
		t.Run(scenario, func(t *testing.T) {
			c, _ := multiFixture(t)
			path := filepath.Join(c.BrokerDir, "layout.bin")
			switch scenario {
			case "count", "duplicate":
				b, _ := os.ReadFile(path)
				if scenario == "count" {
					binary.LittleEndian.PutUint32(b[40:44], 1)
				} else {
					copy(b[144:160], b[64:80])
				}
				os.WriteFile(path, b, 0644)
			case "layout-symlink":
				os.Rename(path, path+".real")
				os.Symlink(path+".real", path)
			case "directory-symlink":
				dir := c.brokerPath(1)
				os.Rename(dir, dir+".real")
				os.Symlink(dir+".real", dir)
			case "writable":
				os.Chmod(filepath.Join(c.BrokerDir, "slots"), 0777)
			}
			if _, e := c.CheckSlot(time.Now(), 1); e == nil {
				t.Fatal("untrusted layout/path accepted")
			}
		})
	}
}

func TestTwoSlotHealthNotifications(t *testing.T) {
	c, records := multiFixture(t)
	if c.BrokerGID == 0 {
		c.BrokerGID = 1000
		for i := 0; i < 2; i++ {
			if e := os.Chown(filepath.Join(c.brokerPath(i), "gpu.sock"), 0, 1000); e != nil {
				t.Fatal(e)
			}
		}
	}
	_, r := fakeKubelet(t, c)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- Run(ctx, c, t.Logf) }()
	registration(t, r)
	dial, stop := context.WithTimeout(ctx, 4*time.Second)
	defer stop()
	conn, e := Dial(dial, filepath.Join(c.PluginDir, "vmweave.sock"))
	if e != nil {
		t.Fatal(e)
	}
	defer conn.Close()
	stream, e := api.NewDevicePluginClient(conn).ListAndWatch(dial, &api.Empty{})
	if e != nil {
		t.Fatal(e)
	}
	first, e := stream.Recv()
	if e != nil || len(first.Devices) != 2 || first.Devices[0].Health != api.Healthy || first.Devices[1].Health != api.Healthy {
		t.Fatal(first, e)
	}
	sc := c
	sc.StatusFile = filepath.Join(filepath.Dir(c.StatusFile), "slots", "1", "status.json")
	records[1].Ready = false
	write(t, sc, records[1])
	next, e := stream.Recv()
	if e != nil || next.Devices[0].Health != api.Healthy || next.Devices[1].Health != api.Unhealthy {
		t.Fatal(next, e)
	}
	cancel()
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("shutdown timeout")
	}
}
