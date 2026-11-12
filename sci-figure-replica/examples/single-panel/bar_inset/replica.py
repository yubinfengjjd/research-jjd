"""Reconstruct img06 using transcribed printed numbers, not original data."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _example import render

if __name__ == '__main__':
    raise SystemExit(render('bar_inset', Path(__file__).resolve().parent))
