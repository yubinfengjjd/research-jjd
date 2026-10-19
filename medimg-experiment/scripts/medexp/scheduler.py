"""Single-instance detached supervisor. No service/power/account changes."""
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import time

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    __package__='medexp'

from .common import require, safe_path, read_json, write_json, locked, timestamp,adaptive_state_locked
from .process import process_identity, is_alive, spawn_detached


@contextmanager
def step_lock(root):
    # Reuse the controller's OS byte lock in a distinct control directory.
    directory=root/'adaptive';directory.mkdir(exist_ok=True)
    with locked(directory):yield


def start(root):
    from .adaptive import status, TERMINAL
    with locked(root),adaptive_state_locked(root):
        a=read_json(root/'adaptive'/'state.json');old=a.get('scheduler')
        require(a['status'] not in TERMINAL,'当前状态禁止启动调度；主动暂停须明确恢复')
        require(not old or not is_alive(old['pid'],old['token']),'已有本课题归属调度器；禁止重复实例')
        script=Path(__file__).resolve()
        owner=spawn_detached([sys.executable,'-X','utf8',str(script),'--root',str(root)],
                             str(root),str(root/'adaptive'/'scheduler.log'))
        a['scheduler']={**owner,'started_at':timestamp()};write_json(root/'adaptive'/'state.json',a)
    return a


def serve(root):
    from . import adaptive
    # Lifetime ownership lock is separate from per-action lock. Crash releases it.
    directory=root/'adaptive'/'supervisor';directory.mkdir(exist_ok=True)
    with locked(directory):
        while True:
            a=read_json(root/'adaptive'/'state.json')
            if a['status'] in adaptive.TERMINAL:break
            try:a=adaptive.step(root)
            except Exception as exc:
                # Actual failed invocation is preserved, no invented retry/pass.
                a=read_json(root/'adaptive'/'state.json')
                if a['status']=='paused':break
                a.update(status='awaiting_human',stop_reason=type(exc).__name__+': '+str(exc))
                adaptive.persist(root,a,'scheduler_error_requires_human')
                break
            if a['status'] in adaptive.TERMINAL:break
            time.sleep(min(60,adaptive.delegation(root)['budgets']['poll_seconds']))
    return a


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    serve(safe_path(parser.parse_args().root))
