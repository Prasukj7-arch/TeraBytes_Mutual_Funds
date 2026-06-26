import sys
from pathlib import Path

# Ensure project root is in sys.path so we can import services.db
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)

from services.db import *
