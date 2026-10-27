#!/usr/bin/env python3
"""Regression for embedded kernels without CONFIG_TASK_IO_ACCOUNTING."""
import importlib.util
import os
from pathlib import Path
path=Path(__file__).resolve().parents[1]/'scripts/sample-process.py'
spec=importlib.util.spec_from_file_location('sampler',path)
sampler=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampler)
original=sampler.numbers
def without_io(path):
    if str(path).endswith('/io'):
        raise FileNotFoundError('Kernel IO accounting disabled')
    return original(path)
sampler.numbers=without_io
snap=sampler.snapshot(os.getpid())
assert snap['io']=={}
assert snap['status']['VmRSS']>0
assert str(os.getpid()) in snap['threads']
print('PASS: missing process IO accounting retains CPU/memory sampling')
