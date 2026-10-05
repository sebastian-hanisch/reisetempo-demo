"""Gemeinsame Einrichtung der Tests: der Demo-Ordner kommt in den Suchpfad."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
