"""Public blocked-root configuration uses synthetic temporary paths only."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from medexp.common import GateError,safe_path


class PublicPathTests(unittest.TestCase):
    def test_configured_root_and_child_are_rejected_but_prefix_neighbor_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'blocked';root.mkdir()
            with patch.dict(os.environ,{'MEDEXP_BLOCKED_ROOTS':str(root)}):
                for target in (root,root/'child.json'):
                    with self.assertRaises(GateError):safe_path(target)
                self.assertEqual(safe_path(Path(temp)/'blocked-neighbor'),(Path(temp)/'blocked-neighbor').resolve())

    def test_multiple_roots_and_empty_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            roots=[Path(temp)/'first',Path(temp)/'second']
            with patch.dict(os.environ,{'MEDEXP_BLOCKED_ROOTS':os.pathsep.join(map(str,roots))}):
                for root in roots:
                    with self.assertRaises(GateError):safe_path(root/'child')
            with patch.dict(os.environ,{'MEDEXP_BLOCKED_ROOTS':''}):
                self.assertEqual(safe_path(roots[0]),roots[0].resolve())


if __name__=='__main__':unittest.main()
