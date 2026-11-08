#!/usr/bin/env python3
"""Recompute finite/allclose checks from saved tensors, using CPU only."""
import argparse
import json
from pathlib import Path

import torch


def flatten(value, prefix=""):
    if isinstance(value, torch.Tensor):
        return {prefix: value}
    result = {}
    for key, child in value.items():
        result.update(flatten(child, f"{prefix}/{key}"))
    return result


parser = argparse.ArgumentParser()
parser.add_argument("--results", type=Path, default=Path(__file__).parent / "results/20261108")
args = parser.parse_args()
pairs = [(name, f"{name}/cpu.pt", f"{name}/cuda.pt") for name in
         ["candidate-v3b-lstm", "candidate-v3b-lstm-repeat", "candidate-v3b-mlp"]]
pairs += [
    ("continuous", "candidate-v3b-continuous/cpu-continuous.pt", "candidate-v3b-continuous/cuda-continuous.pt"),
    ("resume", "candidate-v3b-continuous/cuda-continuous.pt", "candidate-v3b-resume/cuda-continuous.pt"),
]
checks = []
for case, reference, actual in pairs:
    ref = flatten(torch.load(args.results / reference, map_location="cpu", weights_only=True))
    got = flatten(torch.load(args.results / actual, map_location="cpu", weights_only=True))
    assert ref.keys() == got.keys(), case
    for name, tensor in ref.items():
        other = got[name]
        assert tensor.shape == other.shape and tensor.dtype == other.dtype, (case, name)
        finite = bool(torch.isfinite(tensor).all() and torch.isfinite(other).all())
        passed = finite and torch.allclose(tensor, other, rtol=1e-4, atol=1e-6)
        checks.append(dict(case=case, tensor=name, finite=finite, pass_=passed,
                           max_abs=(tensor - other).abs().max().item()))
report = dict(torch=str(torch.__version__), device="cpu", rtol=1e-4, atol=1e-6,
              passed=all(row["pass_"] for row in checks), checks=checks)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
