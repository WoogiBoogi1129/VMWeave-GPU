// Package plugin exposes fixed VMWeave broker slots to the guest kubelet.
package plugin

import (
	"context"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	api "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

const Resource = "vmweave.io/gpu"
const DeviceID = "vmweave-slot-0"

var hex32 = regexp.MustCompile(`^[0-9a-f]{32}$`)
var hex64 = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Config struct {
	PluginDir, StatusFile, BrokerDir, LibrarySHA256 string
	BrokerGID                                       int
	SlotCount                                       int
	OwnerUID                                        uint32
	BootID                                          string
	MaxAge                                          time.Duration
	Poll                                            time.Duration
}

func (c Config) slots() int {
	if c.SlotCount == 0 {
		return 1
	}
	return c.SlotCount
}

func (c Config) Validate() error {
	if c.slots() < 1 || c.slots() > 2 {
		return errors.New("one or two fixed slots required")
	}
	if !hex64.MatchString(c.LibrarySHA256) || c.BrokerGID <= 0 || c.BootID == "" || c.MaxAge <= 0 || c.Poll <= 0 {
		return errors.New("library SHA256, positive broker GID, boot ID and positive timeouts required")
	}
	for _, p := range []string{c.PluginDir, c.StatusFile, c.BrokerDir} {
		if !filepath.IsAbs(p) || filepath.Clean(p) != p || p == "/" {
			return errors.New("clean absolute non-root paths required")
		}
	}
	if len(filepath.Join(c.PluginDir, "vmweave.sock")) >= 108 {
		return errors.New("plugin socket path too long")
	}
	return nil
}

type Discovery struct {
	SlotIndex           *int    `json:"slotIndex,omitempty"`
	SlotCount           int     `json:"slotCount,omitempty"`
	SessionID           string  `json:"sessionID,omitempty"`
	SchemaVersion       int     `json:"schemaVersion"`
	BrokerProtocol      int     `json:"brokerProtocol"`
	Allocation          string  `json:"allocation"`
	Generation          string  `json:"generation"`
	BootID              string  `json:"bootID"`
	LibrarySHA256       string  `json:"librarySHA256"`
	MaxClients          int     `json:"maxClients"`
	Ready               bool    `json:"ready"`
	Reason              string  `json:"reason"`
	ObservedAt          float64 `json:"observedAt"`
	TransportObservedAt float64 `json:"transportObservedAt"`
	ActiveClient        bool    `json:"activeClient"`
}

func trusted(info os.FileInfo, uid uint32) bool {
	st, ok := info.Sys().(*syscall.Stat_t)
	return ok && st.Uid == uid && info.Mode().Perm()&0022 == 0
}
func (c Config) Check(now time.Time) (Discovery, error) { return c.CheckSlot(now, 0) }

func trustedDir(path string, uid uint32) error {
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !info.IsDir() || !trusted(info, uid) {
		return errors.New("untrusted binding directory")
	}
	return nil
}
func (c Config) brokerPath(slot int) string {
	if c.slots() == 1 {
		return c.BrokerDir
	}
	return filepath.Join(c.BrokerDir, "slots", fmt.Sprint(slot))
}
func (c Config) CheckSlot(now time.Time, slot int) (Discovery, error) {
	if slot < 0 || slot >= c.slots() || c.slots() > 2 {
		return Discovery{}, errors.New("unknown slot")
	}
	var binding []byte
	if c.slots() > 1 {
		for _, dir := range []string{c.BrokerDir, filepath.Join(c.BrokerDir, "slots"), c.brokerPath(slot), filepath.Dir(c.StatusFile), filepath.Join(filepath.Dir(c.StatusFile), "slots")} {
			if err := trustedDir(dir, c.OwnerUID); err != nil {
				return Discovery{}, err
			}
		}
		fd, err := syscall.Open(filepath.Join(c.BrokerDir, "layout.bin"), syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		if err != nil {
			return Discovery{}, err
		}
		f := os.NewFile(uintptr(fd), "layout.bin")
		defer f.Close()
		info, err := f.Stat()
		if err != nil {
			return Discovery{}, err
		}
		if !info.Mode().IsRegular() || !trusted(info, c.OwnerUID) || info.Size() != int64(64+80*c.slots()) {
			return Discovery{}, errors.New("untrusted boot layout")
		}
		binding, err = io.ReadAll(io.LimitReader(f, 225))
		if err != nil || len(binding) != 64+80*c.slots() || binary.LittleEndian.Uint32(binding[40:44]) != uint32(c.slots()) {
			return Discovery{}, errors.New("layout slot count mismatch")
		}
		first := hex.EncodeToString(binding[64:80])
		second := hex.EncodeToString(binding[144:160])
		if first == second || first == strings.Repeat("0", 32) || second == strings.Repeat("0", 32) {
			return Discovery{}, errors.New("invalid layout sessions")
		}
		c.StatusFile = filepath.Join(filepath.Dir(c.StatusFile), "slots", fmt.Sprint(slot), "status.json")
		c.BrokerDir = c.brokerPath(slot)
	}
	return c.checkRecord(now, slot, binding)
}
func (c Config) checkRecord(now time.Time, slot int, binding []byte) (Discovery, error) {
	var d Discovery
	parent, e := os.Lstat(filepath.Dir(c.StatusFile))
	if e != nil {
		return d, e
	}
	if !parent.IsDir() || !trusted(parent, c.OwnerUID) {
		return d, errors.New("untrusted discovery directory")
	}
	fd, e := syscall.Open(c.StatusFile, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if e != nil {
		return d, e
	}
	f := os.NewFile(uintptr(fd), c.StatusFile)
	defer f.Close()
	info, e := f.Stat()
	if e != nil {
		return d, e
	}
	if !info.Mode().IsRegular() || info.Size() > 8192 || !trusted(info, c.OwnerUID) {
		return d, errors.New("untrusted discovery file")
	}
	dec := json.NewDecoder(io.LimitReader(f, 8193))
	if e = dec.Decode(&d); e != nil {
		return d, e
	}
	var extra any
	if dec.Decode(&extra) != io.EOF {
		return d, errors.New("trailing discovery data")
	}
	version := 1
	if len(binding) != 0 {
		version = 2
	}
	if d.SchemaVersion != version || d.BrokerProtocol != 1 || d.MaxClients != 1 || !d.Ready {
		return d, fmt.Errorf("broker unavailable or unsupported: %s", d.Reason)
	}
	if !hex32.MatchString(d.Allocation) || !hex32.MatchString(d.Generation) || d.Allocation == strings.Repeat("0", 32) || d.Generation == strings.Repeat("0", 32) {
		return d, errors.New("invalid binding identity")
	}
	if len(binding) != 0 && (d.SlotIndex == nil || *d.SlotIndex != slot || d.SlotCount != c.slots() ||
		d.SessionID != hex.EncodeToString(binding[64+80*slot:80+80*slot]) ||
		d.Allocation != hex.EncodeToString(binding[:16]) || d.Generation != hex.EncodeToString(binding[16:32])) {
		return d, errors.New("discovery does not match boot slot binding")
	}
	if d.BootID != c.BootID || d.LibrarySHA256 != c.LibrarySHA256 {
		return d, errors.New("boot or library mismatch")
	}
	for _, stamp := range []float64{d.ObservedAt, d.TransportObservedAt} {
		age := float64(now.UnixNano())/1e9 - stamp
		if stamp <= 0 || age < -1 || age > c.MaxAge.Seconds() {
			return d, errors.New("expired or future broker observation")
		}
	}
	s, e := os.Lstat(filepath.Join(c.BrokerDir, "gpu.sock"))
	if e != nil {
		return d, e
	}
	st, ok := s.Sys().(*syscall.Stat_t)
	if !ok || s.Mode()&os.ModeSocket == 0 || st.Uid != c.OwnerUID || int(st.Gid) != c.BrokerGID || s.Mode().Perm()&0007 != 0 || s.Mode().Perm()&0060 != 0060 {
		return d, errors.New("broker socket type/owner/GID/mode mismatch")
	}
	return d, nil
}

type Server struct {
	api.UnimplementedDevicePluginServer
	Config Config
}

func (s *Server) GetDevicePluginOptions(context.Context, *api.Empty) (*api.DevicePluginOptions, error) {
	return &api.DevicePluginOptions{}, nil
}
func (s *Server) ListAndWatch(_ *api.Empty, stream api.DevicePlugin_ListAndWatchServer) error {
	tick := time.NewTicker(s.Config.Poll)
	defer tick.Stop()
	previous := ""
	for {
		devices := []*api.Device{}
		signature := ""
		for slot := 0; slot < s.Config.slots(); slot++ {
			health := api.Healthy
			if _, e := s.Config.CheckSlot(time.Now(), slot); e != nil {
				health = api.Unhealthy
			}
			devices = append(devices, &api.Device{ID: fmt.Sprintf("vmweave-slot-%d", slot), Health: health})
			signature += health + "/"
		}
		if signature != previous {
			if e := stream.Send(&api.ListAndWatchResponse{Devices: devices}); e != nil {
				return e
			}
			previous = signature
		}
		select {
		case <-stream.Context().Done():
			return stream.Context().Err()
		case <-tick.C:
		}
	}
}
func (s *Server) Allocate(ctx context.Context, req *api.AllocateRequest) (*api.AllocateResponse, error) {
	if req == nil || len(req.ContainerRequests) == 0 {
		return nil, status.Error(codes.InvalidArgument, "container requests required")
	}
	result := &api.AllocateResponse{}
	seen := map[int]bool{}
	for _, request := range req.ContainerRequests {
		if request == nil || len(request.DevicesIds) != 1 {
			return nil, status.Error(codes.InvalidArgument, "one known slot per container required")
		}
		slot := -1
		for i := 0; i < s.Config.slots(); i++ {
			if request.DevicesIds[0] == fmt.Sprintf("vmweave-slot-%d", i) {
				slot = i
			}
		}
		if slot < 0 || seen[slot] {
			return nil, status.Error(codes.InvalidArgument, "unknown or repeated slot")
		}
		seen[slot] = true
		if _, e := s.Config.CheckSlot(time.Now(), slot); e != nil {
			return nil, status.Error(codes.Unavailable, e.Error())
		}
		result.ContainerResponses = append(result.ContainerResponses, &api.ContainerAllocateResponse{
			Envs:   map[string]string{"VMWEAVE_BROKER_SOCKET": "/run/vmweave/gpu.sock"},
			Mounts: []*api.Mount{{HostPath: s.Config.brokerPath(slot), ContainerPath: "/run/vmweave", ReadOnly: true}},
		})
	}
	return result, nil
}

func (s *Server) GetPreferredAllocation(context.Context, *api.PreferredAllocationRequest) (*api.PreferredAllocationResponse, error) {
	return &api.PreferredAllocationResponse{}, nil
}
func (s *Server) PreStartContainer(context.Context, *api.PreStartContainerRequest) (*api.PreStartContainerResponse, error) {
	return &api.PreStartContainerResponse{}, nil
}

func Dial(ctx context.Context, path string) (*grpc.ClientConn, error) {
	return grpc.DialContext(ctx, "unix://"+path, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithBlock())
}
func same(path string, info os.FileInfo) bool {
	n, e := os.Lstat(path)
	return e == nil && info != nil && os.SameFile(info, n)
}
func pause(ctx context.Context, d time.Duration) bool {
	select {
	case <-ctx.Done():
		return false
	case <-time.After(d):
		return true
	}
}

// Run holds an advisory lock, serves before registering, and watches both socket
// identities. Kubelet restarts delete sockets; no API-server credentials needed.
func Run(ctx context.Context, c Config, logf func(string, ...any)) error {
	if e := c.Validate(); e != nil {
		return e
	}
	lock, e := os.OpenFile(filepath.Join(c.PluginDir, "vmweave.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		return e
	}
	defer lock.Close()
	if e = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		return fmt.Errorf("another plugin owns this node: %w", e)
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	endpoint := filepath.Join(c.PluginDir, "vmweave.sock")
	kubelet := filepath.Join(c.PluginDir, "kubelet.sock")
	for ctx.Err() == nil {
		if e = os.Remove(endpoint); e != nil && !os.IsNotExist(e) {
			return e
		}
		listener, e := net.Listen("unix", endpoint)
		if e != nil {
			return e
		}
		// Only our own loop removes this path; closing an old listener must not
		// unlink a replacement socket installed after a kubelet restart.
		listener.(*net.UnixListener).SetUnlinkOnClose(false)
		own, _ := os.Lstat(endpoint)
		server := grpc.NewServer()
		api.RegisterDevicePluginServer(server, &Server{Config: c})
		served := make(chan error, 1)
		go func() { served <- server.Serve(listener) }()
		var registered os.FileInfo
		for ctx.Err() == nil && same(endpoint, own) {
			if registered == nil || !same(kubelet, registered) {
				observed, _ := os.Lstat(kubelet)
				attempt, cancel := context.WithTimeout(ctx, 3*time.Second)
				connection, err := Dial(attempt, kubelet)
				if err == nil {
					_, err = api.NewRegistrationClient(connection).Register(attempt, &api.RegisterRequest{Version: api.Version, Endpoint: filepath.Base(endpoint), ResourceName: Resource})
					connection.Close()
				}
				cancel()
				if err == nil && observed != nil && same(kubelet, observed) {
					registered = observed
					logf("registered %s", Resource)
				} else {
					registered = nil
					logf("registration retry: %v", err)
				}
			}
			select {
			case err := <-served:
				server.Stop()
				listener.Close()
				return fmt.Errorf("plugin server stopped: %v", err)
			default:
			}
			if !pause(ctx, c.Poll) {
				break
			}
		}
		server.Stop()
		listener.Close()
		if same(endpoint, own) {
			os.Remove(endpoint)
		}
	}
	return nil
}
