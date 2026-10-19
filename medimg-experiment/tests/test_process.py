"""Real Windows lifecycle tests; no installed process library is required."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    from medexp import process as windows_process
except ImportError:
    windows_process = None


def eventually(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.025)
    return bool(predicate())


@unittest.skipUnless(os.name == "nt", "real Windows process tests")
class OwnedProcessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(windows_process, "Windows process API is not implemented")
        self.directory = tempfile.TemporaryDirectory(prefix="medexp process 眼科-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def launch(self, code, *arguments, env=None):
        process = windows_process.OwnedProcess(
            [sys.executable, "-u", "-c", code, *map(str, arguments)],
            str(self.root),
            dict(os.environ) if env is None else env,
            str(self.root / "training.log"),
        )
        self.addCleanup(process.close)
        return process

    def launch_tree(self):
        pids_file = self.root / "tree.json"
        grandchild = "import time; time.sleep(60)"
        child = (
            "import json,os,pathlib,subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c',sys.argv[2]]); "
            "pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid])); "
            "time.sleep(60)"
        )
        parent = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1],sys.argv[3]]); "
            "time.sleep(60)"
        )
        process = self.launch(parent, pids_file, child, grandchild)
        self.assertTrue(eventually(pids_file.exists), "descendants did not start")
        pids = [process.pid, *json.loads(pids_file.read_text())]
        identities = [(pid, windows_process.process_identity(pid)) for pid in pids]
        self.assertTrue(all(token for _, token in identities))
        return process, identities

    def assert_dead(self, identities):
        self.assertTrue(
            eventually(lambda: all(not windows_process.is_alive(pid, token) for pid, token in identities)),
            f"owned process tree stayed alive: {identities}",
        )

    def test_normal_exit_preserves_exit_code_combines_logs_and_passes_environment(self):
        environment = dict(os.environ, MEDEXP_TEST_VALUE="眼科 test value", PYTHONIOENCODING="utf-8")
        code = (
            "import os,sys; "
            "print(os.getcwd()); "
            "print(os.environ['MEDEXP_TEST_VALUE']); "
            "print('stderr-marker',file=sys.stderr); "
            "print('stdin-eof='+repr(sys.stdin.read())); "
            "sys.exit(7)"
        )
        process = self.launch(code, env=environment)
        self.assertGreater(process.pid, 0)
        self.assertIsInstance(process.token, str)
        self.assertTrue(process.token)
        self.assertEqual(process.wait(timeout=8), 7)
        self.assertEqual(process.poll(), 7)
        self.assertFalse(windows_process.is_alive(process.pid, process.token))
        self.assertIsNone(windows_process.process_identity(process.pid))
        log = (self.root / "training.log").read_bytes()
        self.assertIn(str(self.root).encode(), log)
        self.assertIn("眼科 test value".encode(), log)
        self.assertIn(b"stderr-marker", log)
        self.assertIn(b"stdin-eof=''", log)
        process.close()
        process.close()
        self.assertEqual(process.poll(), 7)

    def test_timeout_does_not_terminate_owned_process(self):
        process = self.launch("import time; time.sleep(60)")
        self.assertIsNone(process.poll())
        with self.assertRaises(subprocess.TimeoutExpired):
            process.wait(timeout=0.01)
        self.assertTrue(windows_process.is_alive(process.pid, process.token))
        process.terminate()
        self.assertIsInstance(process.wait(timeout=8), int)

    def test_creation_token_rejects_stale_pid_identity(self):
        process = self.launch("import time; time.sleep(60)")
        self.assertEqual(windows_process.process_identity(process.pid), process.token)
        self.assertTrue(windows_process.is_alive(process.pid, process.token))
        self.assertFalse(windows_process.is_alive(process.pid, process.token + "-stale"))
        self.assertFalse(windows_process.is_alive(-1, process.token))
        self.assertIsNone(windows_process.process_identity(0))

    def test_terminate_kills_child_and_grandchild_but_not_unrelated_process(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        def cleanup_unrelated():
            if unrelated.poll() is None:
                unrelated.kill()
            unrelated.wait(timeout=8)
        self.addCleanup(cleanup_unrelated)
        process, identities = self.launch_tree()
        process.terminate()
        process.wait(timeout=8)
        self.assert_dead(identities)
        self.assertIsNone(unrelated.poll())
        unrelated.terminate()
        unrelated.wait(timeout=8)

    def test_close_kills_child_and_grandchild(self):
        process, identities = self.launch_tree()
        process.close()
        self.assert_dead(identities)
        process.close()
        self.assertIsInstance(process.poll(), int)

    def test_close_cleans_descendant_after_training_root_exits_normally(self):
        child_info = self.root / "orphan.json"
        child = (
            "import os,pathlib,sys,time; "
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
        )
        training = (
            "import pathlib,subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1]]); "
            "path=pathlib.Path(sys.argv[1]); "
            "exec('while not path.exists():\\n time.sleep(0.025)')"
        )
        process = self.launch(training, child_info, child)
        self.assertEqual(process.wait(timeout=8), 0)
        child_pid = int(child_info.read_text())
        child_token = windows_process.process_identity(child_pid)
        self.assertIsNotNone(child_token)
        process.close()
        self.assert_dead([(child_pid, child_token)])

    def test_exit_code_259_is_an_exit_not_a_running_process(self):
        process = self.launch("import sys; sys.exit(259)")
        self.assertEqual(process.wait(timeout=8), 259)
        self.assertEqual(process.poll(), 259)

    def test_worker_crash_closes_job_and_kills_owned_descendants(self):
        worker_info = self.root / "worker.json"
        tree_info = self.root / "tree.json"
        child = (
            "import json,os,pathlib,subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid])); "
            "time.sleep(60)"
        )
        training = (
            "import subprocess,sys,time; "
            "subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1]]); "
            "time.sleep(60)"
        )
        worker_code = (
            "import json,os,pathlib,sys,time; sys.path.insert(0,sys.argv[1]); "
            "from medexp.process import OwnedProcess; "
            "p=OwnedProcess([sys.executable,'-c',sys.argv[5],sys.argv[3],sys.argv[6]],"
            "sys.argv[2],dict(os.environ),sys.argv[4]); "
            "pathlib.Path(sys.argv[7]).write_text(json.dumps({'pid':p.pid,'token':p.token})); "
            "time.sleep(60)"
        )
        worker = subprocess.Popen(
            [sys.executable, "-c", worker_code, str(SCRIPTS), str(self.root), str(tree_info),
             str(self.root / "crash.log"), training, child, str(worker_info)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.addCleanup(lambda: worker.poll() is None and worker.kill())
        try:
            self.assertTrue(eventually(lambda: worker_info.exists() and tree_info.exists()),
                            "worker failed to create its owned tree")
            root_identity = json.loads(worker_info.read_text())
            identities = [(root_identity["pid"], root_identity["token"])]
            identities.extend((pid, windows_process.process_identity(pid))
                              for pid in json.loads(tree_info.read_text()))
            self.assertTrue(all(token for _, token in identities))
            worker.kill()
            worker.wait(timeout=8)
            self.assert_dead(identities)
        finally:
            if worker.poll() is None:
                worker.kill()
            worker.communicate(timeout=8)

    def test_detached_worker_survives_launcher_exit(self):
        info_file = self.root / "detached.json"
        stop_file = self.root / "stop"
        detached_log = self.root / "detached.log"
        worker_code = (
            "import pathlib,sys,time; print('detached-ready',flush=True); "
            "stop=pathlib.Path(sys.argv[1]); "
            "exec('while not stop.exists():\\n time.sleep(0.025)')"
        )
        launcher_code = (
            "import json,pathlib,sys; sys.path.insert(0,sys.argv[1]); "
            "from medexp.process import spawn_detached; "
            "info=spawn_detached([sys.executable,'-u','-c',sys.argv[5],sys.argv[4]],"
            "sys.argv[2],sys.argv[3]); "
            "pathlib.Path(sys.argv[6]).write_text(json.dumps(info))"
        )
        result = subprocess.run(
            [sys.executable, "-c", launcher_code, str(SCRIPTS), str(self.root),
             str(detached_log), str(stop_file), worker_code, str(info_file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        info = json.loads(info_file.read_text())
        try:
            self.assertTrue(windows_process.is_alive(info["pid"], info["token"]))
            self.assertTrue(eventually(lambda: detached_log.exists() and b"detached-ready" in detached_log.read_bytes()))
            self.assertTrue(windows_process.is_alive(info["pid"], info["token"]))
        finally:
            stop_file.touch()
            self.assertTrue(eventually(lambda: not windows_process.is_alive(info["pid"], info["token"])))


if __name__ == "__main__":
    unittest.main()
