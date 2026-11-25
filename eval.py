#!/usr/bin/env python3
"""Thin wrapper so the benchmark can be run as `python eval.py`."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.eval import main
sys.exit(main())
