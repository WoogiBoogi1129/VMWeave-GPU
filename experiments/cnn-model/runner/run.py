#!/usr/bin/env python3
"""Run staged CNN learning with the established paired-runtime collector."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cnn_runner',HERE.parent/'cnn-forward/runner/run.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':
    module.main(workload_root=HERE,namespace_prefix='cnn-model-',
                cases=('relu','pool','cnn','mnist'),pod_deadline=480,
                extra_sources={'mnist.b64':(HERE.parent/'rnn-default/data/mnist.b64').read_text()})
