package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"

	api "github.com/WoogiBoogi1129/VMWeave-GPU/operator/api/v1alpha1"
	"github.com/WoogiBoogi1129/VMWeave-GPU/operator/internal/engine"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/validation"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
	"sigs.k8s.io/controller-runtime/pkg/webhook"
	"sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

func main() {
	component := flag.String("component", "controller", "controller or webhook")
	mode := flag.String("mode", "review", "review or active")
	ns := flag.String("namespaces", "", "comma-separated managed namespaces")
	system := flag.String("system-namespace", "vmweave-system", "operator namespace")
	sa := flag.String("controller-service-account", "vmweave-controller", "controller service account")
	cert := flag.String("cert-dir", "/tls", "TLS cert directory")
	leader := flag.Bool("leader-elect", true, "use Lease election")
	metricsAddr := flag.String("metrics-bind-address", ":8080", "metrics listener")
	healthAddr := flag.String("health-bind-address", ":8081", "health listener")
	flag.Parse()
	ctrl.SetLogger(zap.New())
	if *mode != "review" && *mode != "active" {
		panic("invalid mode")
	}
	if *component != "controller" && *component != "webhook" {
		panic("invalid component")
	}
	scopes := map[string]bool{}
	caches := map[string]cache.Config{}
	for _, s := range strings.Split(*ns, ",") {
		s = strings.TrimSpace(s)
		if len(validation.IsDNS1123Label(s)) > 0 || s == *system {
			panic("invalid workload namespace: " + s)
		}
		scopes[s] = true
		caches[s] = cache.Config{}
	}
	scheme := runtime.NewScheme()
	_ = clientgoscheme.AddToScheme(scheme)
	_ = api.AddToScheme(scheme)
	cfg := ctrl.GetConfigOrDie()
	direct, e := client.New(cfg, client.Options{Scheme: scheme})
	if e != nil {
		panic(e)
	}
	mgr, e := ctrl.NewManager(cfg, ctrl.Options{Scheme: scheme, Client: client.Options{Cache: &client.CacheOptions{Unstructured: true}}, Cache: cache.Options{DefaultNamespaces: caches}, Metrics: metricsserver.Options{BindAddress: *metricsAddr}, HealthProbeBindAddress: *healthAddr, LeaderElection: *leader && *component == "controller", LeaderElectionID: "vmweave-controller", LeaderElectionNamespace: *system, LeaderElectionReleaseOnCancel: true, WebhookServer: webhook.NewServer(webhook.Options{Port: 9443, CertDir: *cert})})
	if e != nil {
		panic(e)
	}
	if *component == "controller" {
		tol := []interface{}{}
		if raw := os.Getenv("VMWEAVE_WORKLOAD_TOLERATIONS"); raw != "" {
			if e = json.Unmarshal([]byte(raw), &tol); e != nil {
				panic(e)
			}
		}
		r := &engine.Reconciler{Client: mgr.GetClient(), Reader: mgr.GetAPIReader(), Namespaces: scopes, Options: engine.Options{Mode: *mode, Tolerations: tol}}
		if e = r.Setup(mgr); e != nil {
			panic(e)
		}
	} else {
		mgr.GetWebhookServer().Register("/validate", &admission.Webhook{Handler: admission.HandlerFunc(func(ctx context.Context, r admission.Request) admission.Response {
			if !scopes[r.Namespace] {
				return admission.Denied("namespace outside management scope")
			}
			a := engine.API{C: direct, R: direct, Namespace: r.Namespace, Context: ctx}
			if e := a.Validate(r.AdmissionRequest, *system, *sa); e != nil {
				return admission.Denied(e.Error())
			}
			return admission.Allowed("validated")
		})})
	}
	if e = mgr.AddHealthzCheck("health", healthz.Ping); e != nil {
		panic(e)
	}
	if *component == "webhook" {
		e = mgr.AddReadyzCheck("webhook", mgr.GetWebhookServer().StartedChecker())
	} else {
		e = mgr.AddReadyzCheck("cache", func(req *http.Request) error {
			if !mgr.GetCache().WaitForCacheSync(req.Context()) {
				return fmt.Errorf("cache not synced")
			}
			return nil
		})
	}
	if e != nil {
		panic(e)
	}
	ctrl.Log.Info("starting", "component", *component, "mode", *mode, "namespaces", *ns)
	if e = mgr.Start(ctrl.SetupSignalHandler()); e != nil {
		panic(e)
	}
}
