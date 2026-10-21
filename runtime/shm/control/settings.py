"""Configuration shared by the CPU-only control-plane entrypoints."""
import vmweave_env as env
import os
import re


def namespace():
    value = env.require('VMWEAVE_NAMESPACE')
    if not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?', value):
        raise ValueError('VMWEAVE_NAMESPACE must be a Kubernetes namespace name')
    return value


def mode():
    value = env.get('VMWEAVE_MODE', 'review')
    if value not in ('review', 'active'):
        raise ValueError('VMWEAVE_MODE must be review or active')
    return value


def positive_float(name, default):
    value = float(env.get(name, str(default)))
    if not 0 < value <= 3600:
        raise ValueError(name + ' must be in (0, 3600]')
    return value
