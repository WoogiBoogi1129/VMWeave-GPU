"""Deployment contract tests: rendering, policy propagation and preflight failures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[2]


def render(*args, success=True):
    cmd = ["helm", "template", "alternate", str(ROOT / "charts/vmweave-operator"),
           "--namespace", "control-other",
           "--set", "image.digest=sha256:" + "a" * 64,
           "--set", "management.namespaces={tenant}",
           *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if success and result.returncode:
        raise AssertionError(result.stderr)
    return list(yaml.safe_load_all(result.stdout)) if success else result


class ChartTests(unittest.TestCase):
    def test_existing_ca_required(self):
        self.assertNotEqual(render(success=False).returncode, 0)

    def test_existing_tls_and_pull_secrets(self):
        docs = render("--set", "tls.caBundle=dGVzdA==",
                      "--set", "imagePullSecrets[0].name=control-pull",
                      "--set", "workloads.imagePullSecrets[0].name=tenant-pull")
        webhook = next(x for x in docs if x["kind"] == "ValidatingWebhookConfiguration")
        self.assertEqual(webhook["webhooks"][0]["clientConfig"]["caBundle"], "dGVzdA==")
        self.assertEqual(webhook["webhooks"][0]["clientConfig"]["service"]["name"], "alternate-webhook")
        self.assertEqual(webhook["webhooks"][0]["clientConfig"]["service"]["namespace"], "control-other")
        self.assertFalse(any(x["kind"] == "Certificate" for x in docs))
        controller = next(x for x in docs if x["kind"] == "Deployment" and x["metadata"]["name"] == "alternate-controller")
        spec = controller["spec"]["template"]["spec"]
        self.assertEqual(spec["imagePullSecrets"], [{"name": "control-pull"}])
        env = {x["name"]: x["value"] for x in spec["containers"][0]["env"]}
        self.assertEqual(json.loads(env["VMWEAVE_WORKLOAD_IMAGE_PULL_SECRETS"]), [{"name": "tenant-pull"}])

    def test_cert_manager_release_dns_and_injection(self):
        docs = render("--set", "tls.mode=certManager", "--set", "tls.certManager.issuerRef.name=test-ca")
        cert = next(x for x in docs if x["kind"] == "Certificate")
        self.assertEqual(cert["spec"]["dnsNames"], ["alternate-webhook.control-other.svc"])
        webhook = next(x for x in docs if x["kind"] == "ValidatingWebhookConfiguration")
        self.assertEqual(webhook["metadata"]["annotations"]["cert-manager.io/inject-ca-from"],
                         "control-other/alternate-webhook")
        self.assertNotIn("caBundle", webhook["webhooks"][0]["clientConfig"])

    def test_cert_manager_requires_issuer(self):
        self.assertNotEqual(render("--set", "tls.mode=certManager", success=False).returncode, 0)

    def test_staged_install_has_no_webhook_registration(self):
        docs = render("--set", "tls.mode=certManager", "--set", "tls.certManager.issuerRef.name=test",
                      "--set", "webhook.registrationEnabled=false")
        self.assertTrue(any(x["kind"] == "Certificate" for x in docs))
        self.assertFalse(any(x["kind"] == "ValidatingWebhookConfiguration" for x in docs))

    def test_empty_secret_name_rejected(self):
        self.assertNotEqual(render("--set", "tls.caBundle=dGVzdA==", "--set-json",
                                   'workloads.imagePullSecrets=[{"name":""}]', success=False).returncode, 0)


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("preflight", ROOT / "scripts/operator/preflight.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_unready_and_missing_gpu_are_not_success(self):
        self.assertTrue(self.module.evaluate_node({}))

    def test_dra_does_not_require_classic_extended_resources(self):
        node = {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        self.assertEqual(self.module.evaluate_node(node, "hami-dra"), [])
        self.assertTrue(self.module.evaluate_node(node, "hami"))
        node["status"]["conditions"].append({"type": "DiskPressure", "status": "True"})
        self.assertIn("DiskPressure", self.module.evaluate_node(node, "hami-dra"))

    def test_hami_resources_and_ready(self):
        node = {"status": {"conditions": [{"type": "Ready", "status": "True"}],
                           "allocatable": {"nvidia.com/gpu": "1", "nvidia.com/gpumem": "8192",
                                           "nvidia.com/gpucores": "100"}}}
        self.assertEqual(self.module.evaluate_node(node), [])
        node["status"]["conditions"].append({"type": "DiskPressure", "status": "True"})
        self.assertIn("DiskPressure", self.module.evaluate_node(node))
        node["spec"] = {"unschedulable": True}
        self.assertIn("node is cordoned", self.module.evaluate_node(node))


class SmokeTests(unittest.TestCase):
    def run_smoke(self, replace_vm=False, cycle=False, fail_ssh=False):
        spec = importlib.util.spec_from_file_location("smoke", ROOT / "scripts/operator/smoke-vm.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        state = {"running": True, "generation": 1, "vm_reads": 0, "patches": []}

        def output(args, **kwargs):
            op = args[3]
            if op == "patch":
                data = json.loads(args[-1])
                self.assertEqual(data[0], {"op": "test", "path": "/metadata/uid", "value": "vm-uid"})
                value = data[1]["value"]
                state["patches"].append(value)
                state["running"] = value == "Always"
                if state["running"]:
                    state["generation"] += 1
                return "{}"
            kind = args[4]
            if kind == "vm":
                state["vm_reads"] += 1
                uid = "replaced" if replace_vm and state["vm_reads"] > 1 else "vm-uid"
                return json.dumps({"metadata": {"uid": uid}})
            if kind == "sharedmemorychannels.vmweave.io":
                return json.dumps({"metadata": {"uid": "channel-uid"},
                    "spec": {"lifecycle": "VM", "vmRef": {"uid": "vm-uid"}},
                    "status": {"phase": "Ready" if state["running"] else "Stopped",
                               "allocation": str(state["generation"]), "workerPodUID": "worker",
                               "vmiUID": "vmi"}})
            if kind == "vmi":
                return json.dumps({"metadata": {"uid": "vmi"}, "status": {"interfaces": [
                    {"ipAddress": "192.0.2.1"}]}}) if state["running"] else ""
            if kind == "pods":
                return '{"items":[]}'
            raise AssertionError(args)

        def run(args, **kwargs):
            if args[-1] == "true":
                return subprocess.CompletedProcess(args, 0)
            return subprocess.CompletedProcess(args, 1 if fail_ssh else 0,
                '{"status":"PASS","kernel_repeats":100}\n', "failed" if fail_ssh else "")

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "result"
            argv = ["smoke-vm.py", "--namespace", "tenant", "--vm", "test",
                    "--key", "/tmp/not-used", "--output", str(dest)]
            if cycle:
                argv.append("--cycle-disposable-vm")
            with patch("sys.argv", argv), patch.object(module.subprocess, "check_output", side_effect=output), \
                 patch.object(module.subprocess, "run", side_effect=run):
                if replace_vm or fail_ssh:
                    with self.assertRaises(RuntimeError):
                        module.main()
                else:
                    module.main()
            events = json.loads((dest / "events.json").read_text())
        return state, events

    def test_default_does_not_patch_vm(self):
        state, events = self.run_smoke()
        self.assertEqual(state["patches"], [])
        self.assertEqual([e["event"] for e in events], ["first", "second", "PASS"])

    def test_cycle_finishes_halted_with_fresh_allocation(self):
        state, events = self.run_smoke(cycle=True)
        self.assertEqual(state["patches"], ["Halted", "Always", "Halted"])
        self.assertFalse(state["running"])
        self.assertEqual(events[-1]["event"], "PASS")

    def test_identity_replacement_aborts(self):
        state, events = self.run_smoke(replace_vm=True)
        self.assertEqual(state["patches"], [])
        self.assertEqual(events[-1]["event"], "FAIL")

    def test_failed_program_does_not_report_pass(self):
        state, events = self.run_smoke(fail_ssh=True)
        self.assertEqual(state["patches"], [])
        self.assertEqual(events[-1]["event"], "FAIL")


class ReleaseTests(unittest.TestCase):
    def test_mixed_revision_does_not_write_lock(self):
        spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/operator/release-manifest.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "lock.json"
            argv = ["release-manifest.py", "--repository", "registry.example/test", "--tag", "v0.3.0",
                    "--source-revision", "a" * 40, "--output", str(dest)]
            metadata = {"Digest": "sha256:" + "b" * 64,
                        "Labels": {"org.opencontainers.image.revision": "c" * 40}}
            with patch("sys.argv", argv), patch.object(module.subprocess, "check_output",
                                                       return_value=json.dumps(metadata)):
                with self.assertRaisesRegex(ValueError, "revision label mismatch"):
                    module.main()
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
