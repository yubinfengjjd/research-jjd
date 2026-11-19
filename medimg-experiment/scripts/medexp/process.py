"""Managed process runner with Windows Job Object cleanup and POSIX fallback."""
from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
import signal
import subprocess
import time

if os.name == 'nt':
    from ctypes import wintypes
    import _winapi
    import msvcrt

    _kernel = ctypes.WinDLL('kernel32', use_last_error=True)

    class _JobBasicLimits(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_longlong),
            ('PerJobUserTimeLimit', ctypes.c_longlong),
            ('LimitFlags', wintypes.DWORD),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', wintypes.DWORD),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', wintypes.DWORD),
            ('SchedulingClass', wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
            'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount',
        )]

    class _JobExtendedLimits(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', _JobBasicLimits),
            ('IoInfo', _IoCounters),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
        ]

    _kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    _kernel.SetInformationJobObject.restype = wintypes.BOOL
    _kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel.TerminateJobObject.restype = wintypes.BOOL
    _kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    _kernel.ResumeThread.restype = wintypes.DWORD

    def _checked(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def _start_suspended(argv: list[str], cwd: str, env: dict[str, str], log_path: str):
        with open(log_path, 'ab', buffering=0) as log, open(os.devnull, 'rb', buffering=0) as null:
            log_handle = msvcrt.get_osfhandle(log.fileno())
            null_handle = msvcrt.get_osfhandle(null.fileno())
            handles = [log_handle, null_handle]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            startup.hStdInput = null_handle
            startup.hStdOutput = startup.hStdError = log_handle
            startup.lpAttributeList = {'handle_list': handles}
            process, thread, pid, _ = _winapi.CreateProcess(
                None, subprocess.list2cmdline(argv), None, None, True,
                0x00000004 | 0x08000000 | 0x00000400,
                env, cwd, startup,
            )
        return process, thread, pid


def _normalize_python_argv(argv: list[str]) -> list[str]:
    if argv and Path(argv[0]).stem.lower() in ('python', 'python3', 'pythonw') and len(argv) > 1 and argv[1] != '-X':
        return [argv[0], '-X', 'utf8', *argv[1:]]
    return list(argv)


class OwnedProcess:
    """Run one child process (and its descendants) with guaranteed cleanup on timeout/close."""

    def __init__(self, argv: list[str], cwd: str, env: dict[str, str], log_path: str):
        if not argv or any(not isinstance(arg, str) or '\0' in arg for arg in argv):
            raise ValueError('argv must be a nonempty list of strings without NUL characters')
        self._argv = _normalize_python_argv(argv)
        self._returncode: int | None = None
        self._process = None
        self._job = None
        self._popen = None
        self._log_fh = None

        if os.name == 'nt':
            thread = None
            try:
                self._job = _checked(_kernel.CreateJobObjectW(None, None))
                limits = _JobExtendedLimits()
                limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
                _checked(_kernel.SetInformationJobObject(
                    self._job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
                self._process, thread, self._pid = _start_suspended(self._argv, cwd, env, log_path)
                _checked(_kernel.AssignProcessToJobObject(self._job, self._process))
                if _kernel.ResumeThread(thread) == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
            except BaseException:
                if self._process is not None:
                    _winapi.TerminateProcess(self._process, 1)
                    _winapi.WaitForSingleObject(self._process, 5000)
                    _winapi.CloseHandle(self._process)
                    self._process = None
                if self._job is not None:
                    _winapi.CloseHandle(self._job)
                    self._job = None
                raise
            finally:
                if thread is not None:
                    _winapi.CloseHandle(thread)
        else:
            self._log_fh = open(log_path, 'ab')
            self._popen = subprocess.Popen(
                self._argv, cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, stdout=self._log_fh, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self._pid = self._popen.pid

    @property
    def pid(self) -> int:
        return self._pid

    def poll(self) -> int | None:
        if self._returncode is not None:
            return self._returncode
        if os.name == 'nt':
            if self._process is not None and _winapi.WaitForSingleObject(self._process, 0) == _winapi.WAIT_OBJECT_0:
                self._returncode = _winapi.GetExitCodeProcess(self._process)
        else:
            if self._popen is not None:
                self._returncode = self._popen.poll()
        return self._returncode

    def terminate(self) -> None:
        if os.name == 'nt':
            if self._job is not None:
                _kernel.TerminateJobObject(self._job, 1)
        elif self._popen is not None and self._popen.poll() is None:
            try:
                os.killpg(self._popen.pid, signal.SIGTERM)
            except OSError:
                self._popen.terminate()

    def wait(self, timeout: float | None = None) -> int:
        if self.poll() is not None:
            return self._returncode
        if timeout is not None and not math.isfinite(timeout):
            raise ValueError('timeout must be finite or None')
        if os.name == 'nt':
            deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
            while True:
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                ms = _winapi.INFINITE if remaining is None else min(math.ceil(remaining * 1000), 0xFFFFFFFE)
                res = _winapi.WaitForSingleObject(self._process, ms)
                if res == _winapi.WAIT_OBJECT_0:
                    self._returncode = _winapi.GetExitCodeProcess(self._process)
                    return self._returncode
                if res != _winapi.WAIT_TIMEOUT:
                    raise OSError(f'unexpected Windows wait result: {res}')
                if deadline is not None and time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(self._argv, timeout)
        else:
            self._returncode = self._popen.wait(timeout=timeout)
            return self._returncode

    def close(self) -> None:
        if os.name == 'nt':
            if self._job is not None:
                job, self._job = self._job, None
                _winapi.CloseHandle(job)
            if self._process is not None:
                try:
                    self.wait(timeout=5)
                except Exception:
                    pass
                finally:
                    proc, self._process = self._process, None
                    _winapi.CloseHandle(proc)
        else:
            if self._popen is not None and self._popen.poll() is None:
                self.terminate()
                try:
                    self._popen.wait(timeout=5)
                except Exception:
                    try:
                        os.killpg(self._popen.pid, signal.SIGKILL)
                    except OSError:
                        self._popen.kill()
            if self._log_fh is not None:
                fh, self._log_fh = self._log_fh, None
                fh.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
