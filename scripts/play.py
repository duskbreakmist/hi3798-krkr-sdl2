#!/usr/bin/env python3
"""Interactive launcher: persistent saves, memory guard, no diagnostic captures."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import time


SHELL = [
    ('lxqt-panel', ['/usr/bin/lxqt-panel']),
    ('pcmanfm-qt', ['/usr/bin/pcmanfm-qt', '--desktop', '--profile=lxqt']),
    ('lxqt-runner', ['/usr/bin/lxqt-runner']),
    ('lxqt-powermana', ['/usr/bin/lxqt-powermanagement']),
    ('lxqt-policykit-', ['/usr/bin/lxqt-policykit-agent']),
]


def memory():
    return {k: int(v) for k, v in re.findall(r'^(\w+):\s*(\d+)',
            Path('/proc/meminfo').read_text(), re.M)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--data-dir', type=Path, help='Persistent game config and saves')
    parser.add_argument('--session-root', type=Path, help='Local logs directory')
    parser.add_argument('--keep-shell', action='store_true')
    parser.add_argument('--seconds', type=int, default=0, help='0: no time limit')
    parser.add_argument('--gclim', type=int, default=8, help='Graphics cache limit, MiB')
    parser.add_argument('--max-rss-mib', type=int, default=600)
    parser.add_argument('--min-available-mib', type=int, default=96)
    parser.add_argument('--min-noncma-mib', type=int, default=24)
    parser.add_argument('--trace', action='store_true', help='Enable verbose engine tracing')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as the logged-in desktop user, not root')
    game, runtime = args.game.resolve(), args.runtime.resolve()
    if not (game/'data.xp3').is_file() or not (runtime/'kirikiroid2').is_file():
        parser.error('Missing game data.xp3 or runtime kirikiroid2')
    if args.seconds < 0 or args.gclim < 0:
        parser.error('seconds and gclim must be nonnegative')
    key = hashlib.sha256(os.fsencode(game)).hexdigest()[:16]
    data_home = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
    state = (args.data_dir or data_home/'hi3798-krkr'/key).resolve()
    state.mkdir(parents=True, exist_ok=True)
    # One launcher owns this game state. Keep the lock alive until cleanup ends.
    with (state/'session.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('This game data directory already has a running session')
        return run(args, game, runtime, state)


def run(args, game, runtime, state):
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    session = (args.session_root or state/'sessions')/stamp
    session.mkdir(parents=True, exist_ok=False)
    project = session/'project'
    project.mkdir()
    for path in sorted(game.iterdir()):
        if path.name.lower() == 'savedata':
            continue
        if path.is_file():
            if path.suffix.lower() in ('.xp3', '.mp4', '.mpg', '.avi'):
                (project/path.name).symlink_to(path)
            elif path.stat().st_size <= 16*1024*1024:
                shutil.copy2(path, project/path.name)
        elif path.is_dir():
            size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
            if size <= 32*1024*1024:
                shutil.copytree(path, project/path.name)
    savedata = state/'savedata'
    savedata.mkdir(exist_ok=True)
    (project/'savedata').symlink_to(savedata, target_is_directory=True)
    (state/'config').mkdir(exist_ok=True)
    # Preserve the actual desktop environment separately from private game config.
    desktop = os.environ.copy()
    desktop.setdefault('DISPLAY', ':0')
    desktop.setdefault('XAUTHORITY', str(Path.home()/'.Xauthority'))
    desktop.setdefault('XDG_RUNTIME_DIR', '/run/user/%d' % os.getuid())
    desktop.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path='+desktop['XDG_RUNTIME_DIR']+'/bus')
    desktop.setdefault('QT_QPA_PLATFORMTHEME', 'lxqt')
    desktop.setdefault('XDG_CURRENT_DESKTOP', 'LXQt')
    desktop.setdefault('DESKTOP_SESSION', 'lxqt')
    env = dict(desktop)
    env.update(XDG_CONFIG_HOME=str(state/'config'), LD_LIBRARY_PATH=str(runtime/'lib'),
        KRKR_PROJECT=str(project/'data.xp3'), KRKR_BRIEF_ERRORS='1',
        KRKR_FONT_FILE=str(runtime/'fonts/notosanssc.ttf'),
        KRKR_MENU_SCRIPT=str(runtime/'compat/menu-model.tjs'), KRKR_LOG_INFORMS='1',
        KRKR_ARCHIVE_MODE='game', MALLOC_ARENA_MAX='2', KRKR_SDL_SOFTWARE='1',
        LIBGL_ALWAYS_SOFTWARE='1', LP_NUM_THREADS='2')
    for name in ('KRKR_TRACE', 'KRKR_INPUT_TRACE', 'KRKR_FRAME_DUMP'):
        env.pop(name, None)
    if args.trace:
        env.update(KRKR_TRACE='1', KRKR_INPUT_TRACE='1')
    argv = [str(runtime/'kirikiroid2'), str(project)+'/', '-debugwin=no',
            '-datapath='+str(savedata)+'/', '-gclim='+str(args.gclim)]
    result = {'started': datetime.datetime.now().astimezone().isoformat(),
              'argv': argv, 'savedata': str(savedata), 'memory_before': memory()}
    stopped = []
    child = None
    requested = []
    old_handlers = {}
    def request_stop(signum, frame):
        requested.append(signum)
    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    print('Logs: '+str(session), flush=True)
    print('Persistent saves: '+str(savedata), flush=True)
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            old_handlers[signum] = signal.signal(signum, request_stop)
        if not args.keep_shell:
            for comm, command in SHELL:
                found = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', comm],
                    stdout=subprocess.PIPE, text=True, check=False)
                pids = [int(p) for p in found.stdout.split()]
                if pids:
                    stopped.append(command)
                    for pid in pids:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
            time.sleep(2)
        result['memory_after_shell_stop'] = memory()
        with (session/'engine.log').open('w') as log:
            child = subprocess.Popen(argv, env=env, cwd=session, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=no_core)
            start = time.monotonic()
            try:
                while child.poll() is None:
                    if requested:
                        result['stop_reason'] = 'terminal signal'
                        break
                    if args.seconds and time.monotonic()-start >= args.seconds:
                        result['stop_reason'] = 'time limit'
                        break
                    m = memory()
                    try:
                        status = Path('/proc/%d/status' % child.pid).read_text()
                    except FileNotFoundError:
                        continue
                    rss = re.search(r'^VmRSS:\s*(\d+)', status, re.M)
                    normal = m['MemAvailable']-m.get('CmaFree', 0)
                    if (m['MemAvailable'] < args.min_available_mib*1024 or
                        normal < args.min_noncma_mib*1024 or
                        (rss and int(rss.group(1)) > args.max_rss_mib*1024)):
                        result['stop_reason'] = 'memory guard'
                        result['guard_memory'] = m
                        print('Memory guard: stopping game', flush=True)
                        break
                    time.sleep(1)
            finally:
                result['elapsed'] = round(time.monotonic()-start, 2)
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        result['forced_kill'] = True
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                result['returncode'] = child.returncode
    finally:
        for command in stopped:
            try:
                subprocess.Popen(command, env=desktop, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as exc:
                print('Desktop restore failed: '+str(exc), flush=True)
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        result['memory_after'] = memory()
        (session/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if result.get('returncode') == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
