#!/usr/bin/env python3
"""Assemble a local runtime; do not include game assets or system graphics libs."""
from pathlib import Path
import os
import re
import shutil
import subprocess

repo = Path(__file__).resolve().parents[1]
work = Path(os.environ.get('KRKR_WORK', repo/'work')).resolve()
sysroot = Path(os.environ['KRKR_SYSROOT']).resolve()
out = work/'runtime'
if out.exists():
    raise SystemExit('Runtime exists; choose a new work directory or move it aside')
for name in ('lib','fonts','compat','licenses'):
    (out/name).mkdir(parents=True, exist_ok=True)
shutil.copy2(work/'build/krkrsdl2', out/'kirikiroid2')
subprocess.run(['arm-linux-gnueabihf-strip', str(out/'kirikiroid2')], check=True)
source = work/'source'
shutil.copy2(source/'krkrsdl2/data/notosanssc.ttf', out/'fonts/notosanssc.ttf')
compat = source/'compat-patches/system'
original = (compat/'k2compat.tjs').read_text()
menu = original[original.index('class KrkrnsScriptMenuItem {'):original.index('// Native window handles are')]
notifications = original[original.index('if (typeof(global.__krkrns_notifications)'):original.index('// --- Window (windowEx surface)')]
popup = (compat/'menu_popup.tjs').read_text().replace(
    'var fonts = Font.addFont("file://?/romfs:/notosanssc.ttf");\n            if (fonts.count > 0) layer.font.face = fonts[0];',
    'layer.font.face = Font.defaultFaceName;')
(out/'compat/menu-model.tjs').write_text(popup+'\n'+menu+'\n'+notifications+'''
if(typeof(Window.HWND)=="undefined") Window.HWND=0;
if(typeof(Window.setMessageHook)=="undefined") Window.setMessageHook=function(enable, number) { return false; };
''')
skip = re.compile(r'^(ld-linux|lib(c|m|dl|pthread|rt|resolv|util)\.so\.|lib(EGL|GL|GLX|GLdispatch|GLESv1_CM|GLESv2|glapi|gbm)\.so\.)')
index = {}
for base in (sysroot/'lib/arm-linux-gnueabihf', sysroot/'usr/lib/arm-linux-gnueabihf'):
    for path in sorted(base.rglob('*.so*')):
        index.setdefault(path.name, path)
def resolve(path):
    for _ in range(20):
        path = Path(os.path.normpath(path))
        if not path.is_relative_to(sysroot):
            raise RuntimeError('Library escaped sysroot')
        if not path.is_symlink():
            return path
        target = Path(os.readlink(path))
        path = sysroot/str(target).lstrip('/') if target.is_absolute() else path.parent/target
    raise RuntimeError('Library symlink loop')
def needed(path):
    return re.findall(r'\(NEEDED\).*\[(.*?)\]', subprocess.check_output(
        ['arm-linux-gnueabihf-readelf','-d',str(path)], text=True))
todo = needed(out/'kirikiroid2')
seen = set()
while todo:
    name = todo.pop()
    if name in seen or skip.match(name):
        continue
    seen.add(name)
    path = resolve(index[name])
    shutil.copyfile(path, out/'lib'/name)
    todo.extend(needed(path))
for path in source.rglob('*'):
    if path.is_file() and (path.name.lower().startswith(('license','copying','notice')) or
                          path.name.lower() in ('ofl.txt', 'upstream-license.txt')):
        target = out/'licenses'/path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path,target)
copyright_dir = sysroot/'usr/share/doc'
for path in copyright_dir.glob('*/copyright'):
    target = out/'licenses/debian'/path.parent.name/'copyright'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path,target)
shutil.copy2(work/'source-changes.patch', out/'source-changes.patch')
shutil.copy2(repo/'scripts/portable-bootstrap.cpp', out/'portable-bootstrap.cpp')
print('Local runtime: '+str(out))
