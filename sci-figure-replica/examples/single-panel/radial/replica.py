"""Reconstruct img08 using its printed three-decimal values and percentages."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _example import render

if __name__ == '__main__':
    raise SystemExit(render('radial', Path(__file__).resolve().parent))
