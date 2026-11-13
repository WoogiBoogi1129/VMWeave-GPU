package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"github.com/WoogiBoogi1129/VMWeave-GPU/integrations/kubernetes-device-plugin/internal/plugin"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

func main() {
	c := plugin.Config{MaxAge: 10 * time.Second, Poll: time.Second}
	flag.StringVar(&c.PluginDir, "plugin-dir", "/var/lib/kubelet/device-plugins", "guest kubelet device plugin directory")
	flag.StringVar(&c.StatusFile, "status-file", "/run/vmweave-device-plugin/status.json", "passive broker discovery")
	flag.StringVar(&c.BrokerDir, "broker-dir", "/run/vmweave", "guest broker directory (also used as Allocate host path)")
	flag.StringVar(&c.LibrarySHA256, "library-sha256", "", "required supported Guest library SHA256")
	flag.IntVar(&c.SlotCount, "slot-count", 1, "fixed approved slots (1 or 2); checked against boot layout")
	flag.IntVar(&c.BrokerGID, "broker-gid", 0, "required socket group ID; match workload supplementalGroups")
	doctor := flag.Bool("doctor", false, "read-only preflight; never connects to broker or kubelet")
	flag.Parse()
	boot, e := os.ReadFile("/proc/sys/kernel/random/boot_id")
	if e != nil {
		log.Fatal(e)
	}
	c.BootID = strings.TrimSpace(string(boot))
	if e = c.Validate(); e != nil {
		log.Fatal(e)
	}
	if *doctor {
		records := []plugin.Discovery{}
		for slot := 0; slot < c.SlotCount; slot++ {
			d, err := c.CheckSlot(time.Now(), slot)
			if err != nil {
				log.Fatal(err)
			}
			records = append(records, d)
		}
		var report any = records
		if c.SlotCount == 1 {
			report = records[0]
		}
		b, _ := json.Marshal(report)
		fmt.Println(string(b))
		return
	}
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer cancel()
	if e = plugin.Run(ctx, c, log.Printf); e != nil {
		log.Fatal(e)
	}
}
