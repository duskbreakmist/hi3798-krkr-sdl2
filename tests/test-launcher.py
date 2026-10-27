#!/usr/bin/env python3
"""Local Linux lifecycle test with a fake engine; never touches the desktop."""
from pathlib import Path
import json, os, subprocess, sys, tempfile
launcher=Path(__file__).resolve().parents[1]/'scripts/play.py'
with tempfile.TemporaryDirectory(prefix='krkr-launch-test-') as temp:
    root=Path(temp)
    game=root/'game';game.mkdir()
    (game/'data.xp3').touch()
    (game/'savedata').mkdir()
    (game/'savedata/original.txt').write_text('original')
    runtime=root/'runtime';runtime.mkdir()
    engine=runtime/'kirikiroid2'
    engine.write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
save=Path(next(a for a in sys.argv if a.startswith('-datapath=')).split('=',1)[1])
counter=save/'counter'
counter.write_text(str(int(counter.read_text())+1 if counter.exists() else 1))
assert 'KRKR_TRACE' not in os.environ
assert 'KRKR_INPUT_TRACE' not in os.environ
assert 'KRKR_FRAME_DUMP' not in os.environ
assert Path(os.environ['KRKR_PROJECT']).is_file()
''')
    engine.chmod(0o755)
    state=root/'state'
    env=dict(os.environ,KRKR_TRACE='1',KRKR_INPUT_TRACE='1',KRKR_FRAME_DUMP='unexpected.bmp')
    argv=[sys.executable,str(launcher),str(game),'--runtime',str(runtime),
          '--data-dir',str(state),'--keep-shell']
    for _ in range(2):
        subprocess.run(argv,env=env,check=True)
    assert (state/'savedata/counter').read_text()=='2'
    assert (game/'savedata/original.txt').read_text()=='original'
    results=[json.loads(p.read_text()) for p in (state/'sessions').glob('*/result.json')]
    assert len(results)==2 and all(r['returncode']==0 for r in results)
    assert not list(state.rglob('*.xwd'))
    print('PASS: two sessions, persistent saves, original untouched, trace removed, no captures')
