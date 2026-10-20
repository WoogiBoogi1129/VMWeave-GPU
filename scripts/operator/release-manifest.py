#!/usr/bin/env python3
"""Resolve all published deployment images; emit a digest lock, never publish."""
import argparse
import json
import re
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repository", required=True, help="Registry/owner, e.g. ghcr.io/example")
    p.add_argument("--tag", required=True)
    p.add_argument("--source-revision", required=True, help="Full release source commit")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--include-dra", action="store_true", help="Include HAMi DRA driver image")
    a = p.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", a.source_revision):
        p.error("full source revision required")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", a.tag):
        p.error("invalid image tag")
    if a.output.exists():
        p.error("output exists")
    images = {}
    components = ["operator", "helper", "worker", "hook", "guest-artifacts", "hami"]
    if a.include_dra:
        components.append("hami-dra")
    for component in components:
        repo = a.repository.rstrip("/") + "/vmweave-" + component
        metadata = json.loads(subprocess.check_output(
            ["skopeo", "inspect", "docker://" + repo + ":" + a.tag],
            text=True, timeout=120))
        digest = metadata["Digest"]
        if (metadata.get("Labels") or {}).get("org.opencontainers.image.revision") != a.source_revision:
            raise ValueError("source revision label mismatch for " + component)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("invalid digest for " + component)
        images[component] = repo + "@" + digest
    lock = {"sourceRevision": a.source_revision, "tag": a.tag,
            "scope": "Published digests and revision labels checked; labels are not cryptographic provenance. Cluster smoke is separate.",
            "images": images}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(lock, f, indent=2)
    print(a.output)


if __name__ == "__main__":
    main()
