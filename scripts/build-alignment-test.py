#!/usr/bin/env python3
"""Build the actual engine colormap unit with identical options and dead stripping."""
import os
from pathlib import Path
import shlex
import subprocess

repo=Path(__file__).resolve().parents[1]
work=Path(os.environ.get('KRKR_WORK',repo/'work')).resolve()
flags={}
for line in (work/'build/CMakeFiles/krkrsdl2common.dir/flags.make').read_text().splitlines():
    if ' = ' in line:
        key,val=line.split(' = ',1)
        flags[key]=shlex.split(val)
source=work/'source/krkrsdl2/external/krkrz/visual/gl/colormap_sse2.cpp'
out=work/'alignment'
out.mkdir(exist_ok=True)
compiler=os.environ['CXX']
common=flags['CXX_DEFINES']+flags['CXX_INCLUDES']+flags['CXX_FLAGS']
for tag,path in [('old',source.with_name(source.name+'.hi3798-upstream')),('fixed',source)]:
    snapshot=out/('colormap-'+tag+'.cpp')
    snapshot.write_bytes(path.read_bytes())
    obj=out/('colormap-'+tag+'.o')
    subprocess.run([compiler,*common,'-ffunction-sections','-fdata-sections','-c',str(snapshot),'-o',str(obj)],check=True)
    subprocess.run([compiler,*common,'-Wl,--gc-sections',str(repo/'tests/colormap-alignment.cpp'),str(obj),'-o',str(out/('test-'+tag))],check=True)
print('On the ARM target, disable core dumps and run:')
print('ulimit -c 0; ./test-old single   # expected SIGBUS')
print('./test-fixed                   # expected 675840 cases passed')
