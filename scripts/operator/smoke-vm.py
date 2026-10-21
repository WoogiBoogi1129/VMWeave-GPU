#!/usr/bin/env python3
"""Run installed Guest GPU smoke twice; optionally cycle and halt a dedicated test VM."""
import argparse
import ipaddress
import json
import shlex
from pathlib import Path
import subprocess
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--namespace", required=True)
    p.add_argument("--vm", required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--virtctl", type=Path, help="Tunnel SSH through virtctl when Pod IPs are not reachable")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cycle-disposable-vm", action="store_true",
                   help="Halt/restart this dedicated VM and finally leave it Halted")
    p.add_argument("--timeout", type=int, default=300)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    events = []

    def kubectl(*args):
        return subprocess.check_output(["kubectl", "-n", a.namespace, *args], text=True, timeout=30)

    def get(kind, name):
        text = kubectl("get", kind, name, "--ignore-not-found", "-o", "json")
        return json.loads(text) if text.strip() else None

    def record(event, **fields):
        events.append({"utc": time.time(), "event": event, **fields})
        (a.output / "events.json").write_text(json.dumps(events, indent=2))

    channel_kind = "sharedmemorychannels.vmweave.io"
    vm = get("vm", a.vm)
    channel = get(channel_kind, a.vm)
    if not vm or not channel:
        raise RuntimeError("existing dedicated VM and same-named Channel required")
    vm_uid, channel_uid = vm["metadata"]["uid"], channel["metadata"]["uid"]
    if (channel["spec"].get("lifecycle") != "VM"
            or channel["spec"]["vmRef"]["uid"] != vm_uid
            or channel["status"].get("phase") != "Ready"
            or channel["spec"].get("drain")):
        raise RuntimeError("Ready, non-draining VM-lifecycle channel required")

    def current():
        v, c = get("vm", a.vm), get(channel_kind, a.vm)
        if not v or not c or v["metadata"]["uid"] != vm_uid or c["metadata"]["uid"] != channel_uid:
            raise RuntimeError("VM/Channel identity changed")
        return c

    def wait(fn):
        until = time.monotonic() + a.timeout
        while time.monotonic() < until:
            result = fn()
            if result:
                return result
            time.sleep(2)
        raise TimeoutError("see events.json and cluster state")

    def strategy(value):
        current()
        patch = [{"op": "test", "path": "/metadata/uid", "value": vm_uid},
                 {"op": "add", "path": "/spec/runStrategy", "value": value}]
        kubectl("patch", "vm", a.vm, "--type=json", "-p", json.dumps(patch))
        record("runStrategy", value=value)

    def run(label):
        c = current()
        if c["status"].get("phase") != "Ready":
            raise RuntimeError("channel not Ready")
        vmi = get("vmi", a.vm)
        if not vmi or vmi["metadata"]["uid"] != c["status"].get("vmiUID"):
            raise RuntimeError("VMI binding mismatch")
        address = str(ipaddress.ip_address(vmi["status"]["interfaces"][0]["ipAddress"]))
        ssh = ["ssh", "-i", str(a.key.resolve()), "-o", "BatchMode=yes",
               "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
               "-o", "UserKnownHostsFile=" + str((a.output / (label + "-known-hosts")).resolve()),
               "ubuntu@" + address]
        if a.virtctl:
            proxy = shlex.join([str(a.virtctl.resolve()), "-n", a.namespace,
                               "port-forward", "--stdio=true", "vmi/" + a.vm, "22"])
            ssh[1:1] = ["-o", "ProxyCommand=" + proxy]
        wait(lambda: subprocess.run(ssh + ["true"], capture_output=True, timeout=10).returncode == 0)
        command = ("env VMWEAVE_BROKER_SOCKET=/run/vmweave/gpu.sock "
                   "LD_LIBRARY_PATH=/opt/vmweave/lib /opt/vmweave/bin/guest-gpu-smoke 23 2")
        result = subprocess.run(ssh + [command], capture_output=True, text=True, timeout=a.timeout)
        (a.output / (label + ".stdout")).write_text(result.stdout)
        (a.output / (label + ".stderr")).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError("GPU smoke failed: " + label)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        if report.get("status") != "PASS" or report.get("kernel_repeats", 0) < 100:
            raise RuntimeError("missing successful kernel result")
        record(label, channel_uid=channel_uid, allocation=c["status"].get("allocation"),
               worker_uid=c["status"].get("workerPodUID"), result=report)

    def halt():
        before = current()["status"]
        worker_uid = before.get("workerPodUID")
        strategy("Halted")
        wait(lambda: current()["status"].get("phase") == "Stopped" and get("vmi", a.vm) is None)
        def worker_gone():
            pods = json.loads(kubectl("get", "pods", "-o", "json"))["items"]
            return all(x["metadata"]["uid"] != worker_uid for x in pods)
        wait(worker_gone)
        record("stopped", worker_uid=worker_uid, channel_status=current()["status"])

    try:
        run("first")
        run("second")
        if a.cycle_disposable_vm:
            previous = current()["status"].get("allocation")
            halt()
            strategy("Always")
            wait(lambda: current()["status"].get("phase") == "Ready")
            if current()["status"].get("allocation") == previous:
                raise RuntimeError("allocation was reused across boots")
            run("restarted")
            halt()
        record("PASS", scope="GPU sessions and optional VM lifecycle; not performance or HA")
    except Exception as e:
        record("FAIL", error=str(e), recovery="Inspect VM/Channel; no forced cleanup was attempted")
        raise
    print(a.output / "events.json")


if __name__ == "__main__":
    main()
