#!/usr/bin/env python3
"""Read-only cluster checks. Host permissions and GPU execution require a smoke test."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def evaluate_node(node):
    errors = []
    if not any(c["type"] == "Ready" and c["status"] == "True"
               for c in node.get("status", {}).get("conditions", [])):
        errors.append("node is not Ready")
    if node.get("spec", {}).get("unschedulable"):
        errors.append("node is cordoned")
    for c in node.get("status", {}).get("conditions", []):
        if c["type"] in ("DiskPressure", "MemoryPressure", "PIDPressure") and c["status"] == "True":
            errors.append(c["type"])
    resources = node.get("status", {}).get("allocatable", {})
    for key in ("nvidia.com/gpu", "nvidia.com/gpumem", "nvidia.com/gpucores"):
        if int(resources.get(key, "0")) <= 0:
            errors.append("missing allocatable " + key)
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--namespace", action="append", required=True, help="Repeat for workload namespaces")
    p.add_argument("--node", action="append", required=True, help="Repeat for GPU nodes")
    p.add_argument("--runtime-class", default="nvidia")
    p.add_argument("--tls-mode", choices=["existingSecret", "certManager"], default="existingSecret")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("output already exists")
    rows = []

    def check(label, args, validate=lambda x: []):
        try:
            result = subprocess.run(["kubectl", *args, "-o", "json"], capture_output=True,
                                    text=True, timeout=30, check=True)
            problems = validate(json.loads(result.stdout))
            rows.append({"check": label, "status": "FAIL" if problems else "PASS", "details": problems})
        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as e:
            # Do not persist kubeconfigs, Secret contents, or command stdout.
            rows.append({"check": label, "status": "FAIL", "details": [str(e)]})

    for tool in ("kubectl", "helm", "python3"):
        rows.append({"check": tool, "status": "PASS" if shutil.which(tool) else "FAIL"})
    check("KubeVirt CRD", ["get", "crd", "virtualmachines.kubevirt.io"])
    check("KubeVirt Available", ["get", "kubevirts.kubevirt.io", "-A"],
          lambda x: [] if any(any(c.get("type") == "Available" and c.get("status") == "True"
                                for c in i.get("status", {}).get("conditions", []))
                             for i in x.get("items", [])) else ["no Available KubeVirt"])
    check("runtime class", ["get", "runtimeclass", a.runtime_class])
    if a.tls_mode == "certManager":
        check("cert-manager CRD", ["get", "crd", "certificates.cert-manager.io"])
    for ns in a.namespace:
        check("namespace " + ns, ["get", "namespace", ns])
    for node in a.node:
        check("GPU node " + node, ["get", "node", node], evaluate_node)
    manual = [
        "Confirm driver/CUDA compatibility and GPU UUID on each host.",
        "Confirm supported KubeVirt sidecar hook configuration and matching shim image.",
        "Confirm HAMi scheduler is healthy and the patched library is mapped by a fresh Worker.",
        "Confirm local backing directory, filesystem, free space and QEMU UID/GID permissions.",
        "Confirm images and same-namespace pull secrets for Operator, Worker/helper and VM/hook.",
        "Confirm TLS issuer or Secret/CA, admission permissions and workload Pod security policy.",
        "Run GPU smoke: these API checks do not establish GPU functionality or full install readiness.",
    ]
    report = {"status": "FAIL" if any(x["status"] == "FAIL" for x in rows) else "API_CHECKS_PASS",
              "checks": rows, "unverified": manual}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
