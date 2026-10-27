#!/usr/bin/env python3
"""Read-only CPU, fault, memory and IO sampling; output is local diagnostic data."""
import argparse
import json
import os
from pathlib import Path
import re
import time

def numbers(path):
    return {key: int(value) for key,value in re.findall(r'^(\w+):?\s+(\d+)',
        Path(path).read_text(), re.M)}

def stat(path):
    fields = Path(path).read_text().rsplit(')',1)[1].split()
    return {'cpu': int(fields[11])+int(fields[12]), 'major': int(fields[9])}

def snapshot(pid):
    proc = Path('/proc')/str(pid)
    threads = {}
    for task in (proc/'task').iterdir():
        try:
            threads[task.name] = stat(task/'stat')['cpu']
        except FileNotFoundError:
            pass
    try:
        io = numbers(proc/'io')
    except FileNotFoundError:
        # CONFIG_TASK_IO_ACCOUNTING is optional on embedded kernels.
        io = {}
    return {'time': time.monotonic(), 'process': stat(proc/'stat'),
        'status': {k:v for k,v in numbers(proc/'status').items() if k in ('VmRSS','VmSwap','Threads')},
        'memory': {k:v for k,v in numbers('/proc/meminfo').items() if k in ('MemAvailable','SwapFree','CmaFree')},
        'vm': {k:v for k,v in numbers('/proc/vmstat').items() if k in ('pswpin','pswpout','pgmajfault')},
        'io': io, 'threads': threads}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pid',type=int)
    p.add_argument('--seconds',type=int,default=20)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    hz=os.sysconf('SC_CLK_TCK')
    first=previous=snapshot(a.pid)
    rows=[]
    for _ in range(a.seconds):
        time.sleep(1)
        try:
            now=snapshot(a.pid)
        except FileNotFoundError:
            break
        dt=now['time']-previous['time']
        row={'elapsed':round(now['time']-first['time'],2),
            'cpu_percent':round((now['process']['cpu']-previous['process']['cpu'])/hz/dt*100,1),
            'major_faults':now['process']['major']-previous['process']['major'],
            'rss_kib':now['status'].get('VmRSS'), 'process_swap_kib':now['status'].get('VmSwap'),
            'available_kib':now['memory'].get('MemAvailable'),
            'swap_in_pages':now['vm']['pswpin']-previous['vm']['pswpin'],
            'swap_out_pages':now['vm']['pswpout']-previous['vm']['pswpout'],
            'read_bytes':(now['io']['read_bytes']-previous['io']['read_bytes']) if 'read_bytes' in now['io'] else None,
            'write_bytes':(now['io']['write_bytes']-previous['io']['write_bytes']) if 'write_bytes' in now['io'] else None,
            'thread_cpu_percent': {tid:round((ticks-previous['threads'].get(tid,ticks))/hz/dt*100,1)
                for tid,ticks in now['threads'].items()}}
        rows.append(row)
        previous=now
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'cpu_basis':'100 percent per core','samples':rows},indent=2)+'\n')
    print('Samples:',len(rows),'Output:',a.output)

if __name__=='__main__':
    main()
