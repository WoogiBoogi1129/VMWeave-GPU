"""Replay one initialization diagnostic against an explicitly supplied, prepared VM.
Does not create VMs or run throughput measurements. See campaign REPORT.md.
"""
import argparse
import json
import shlex
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-config', type=Path, required=True, help='Local private JSON containing an ssh argv list')
    parser.add_argument('--output', type=Path, required=True, help='New output directory, must not exist')
    parser.add_argument('--mode', choices=['replacement', 'preload'], required=True)
    args = parser.parse_args()
    ssh = json.loads(args.ssh_config.read_text())['ssh']
    if not isinstance(ssh, list) or not ssh or Path(ssh[0]).name != 'ssh':
        parser.error('ssh config must contain an ssh argv list')
    args.output.mkdir(parents=True, exist_ok=False)
    env = ['env', '-u', 'LD_PRELOAD', 'LD_LIBRARY_PATH=/tmp/flyt-test:/opt/flyt-cuda-libs']
    if args.mode == 'preload':
        env = ['env', 'LD_PRELOAD=/tmp/flyt-test/cricket-client.so', 'LD_LIBRARY_PATH=/opt/flyt-cuda-libs:/tmp/flyt-test']
    remote = ['sudo', 'timeout', '-s', 'TERM', '-k', '5', '40', *env, '/opt/torch-venv/bin/python3', '-u', '/tmp/flyt-test/mlp.py']
    try:
        result = subprocess.run([*ssh, shlex.join(remote)], input='quit\n', capture_output=True, text=True, timeout=55)
        (args.output/'process.log').write_text(result.stdout + result.stderr)
        status = {'mode':args.mode, 'returncode':result.returncode, 'timeout_seconds':40, 'measured_conditions':0}
    except subprocess.TimeoutExpired as error:
        def decode(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        (args.output/'process.log').write_text(decode(error.stdout)+decode(error.stderr))
        status = {'mode':args.mode,'transport_timeout':True,'measured_conditions':0}
    (args.output/'status.json').write_text(json.dumps(status, indent=2))
    print(json.dumps(status))


if __name__ == '__main__':
    main()
