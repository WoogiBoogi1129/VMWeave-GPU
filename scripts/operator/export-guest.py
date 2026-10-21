#!/usr/bin/env python3
"""Extract versioned Guest artifacts from an image without starting a container."""
import argparse
import re
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", required=True, help="Digest-pinned guest-artifacts image")
    p.add_argument("--engine", choices=["docker", "podman"], default="docker")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", a.image):
        p.error("digest-pinned image required")
    a.output.mkdir(parents=True, exist_ok=False)
    subprocess.run([a.engine, "pull", a.image], check=True)
    cid = subprocess.check_output([a.engine, "create", a.image, "/bin/true"], text=True).strip()
    try:
        subprocess.run([a.engine, "cp", cid + ":/opt/vmweave/guest/.", str(a.output.resolve())], check=True)
    finally:
        subprocess.run([a.engine, "rm", cid], check=True)
    subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=a.output, check=True)
    (a.output / "image-reference.txt").write_text(a.image + "\n")
    print("Verified artifacts:", a.output)


if __name__ == "__main__":
    main()
