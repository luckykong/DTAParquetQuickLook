import sys
from pathlib import Path

# Make Resources/data_preview.py importable as a plain module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Resources"))
