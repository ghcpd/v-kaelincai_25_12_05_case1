import sys
from pathlib import Path

# Ensure project `src/` directory is importable during tests
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
