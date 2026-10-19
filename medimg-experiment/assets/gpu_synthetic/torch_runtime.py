"""FROZEN dependency loader: explicit process-only site path, no downloads."""
import os
from pathlib import Path
import sys

_dll_handles = []


def load_torch():
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    site = os.environ.get("ME_TORCH_SITE")
    if site:
        path = Path(site).resolve(strict=True)
        if not (path / "torch/__init__.py").is_file():
            raise RuntimeError("explicit dependency site has no torch package")
        sys.path.insert(0, str(path))
        dll = path / "torch/lib"
        if sys.platform == "win32" and dll.is_dir():
            _dll_handles.append(os.add_dll_directory(str(dll)))
    import torch
    if site and Path(torch.__file__).resolve() != (path / "torch/__init__.py").resolve():
        raise RuntimeError("imported torch origin differs from explicit dependency site")
    return torch
