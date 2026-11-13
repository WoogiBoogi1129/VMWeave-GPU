#!/usr/bin/env python3
"""Use the same pinned images, pairing checks and evidence collector as forward."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cnn_forward_runner',HERE.parent/'cnn-forward/runner/run.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if __name__=='__main__':
    module.main(workload_root=HERE,namespace_prefix='cnn-training-',
                cases=('minimal','matrix','input-only','weight-only','accumulate'),pod_deadline=360)
