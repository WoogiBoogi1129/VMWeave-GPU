"""Canonical configuration with read-only fallback to legacy FLYT names."""
import os


def get(name, default=None):
    if name in os.environ:
        return os.environ[name]
    if name.startswith('VMWEAVE_'):
        return os.environ.get('FLYT_' + name[8:], default)
    return os.environ.get(name, default)


def require(name):
    value = get(name)
    if value is None:
        raise KeyError(name)
    return value


def pop(name):
    os.environ.pop(name, None)
    if name.startswith('VMWEAVE_'):
        os.environ.pop('FLYT_' + name[8:], None)
