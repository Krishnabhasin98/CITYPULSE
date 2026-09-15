"""CityPulse backend package.

Importing ``app`` first puts the repository root on ``sys.path`` so the
``ai`` subsystem (classification, duplicate matching, trust, risk, agents) is
importable no matter which module triggers the import first. Doing it here, in
the package ``__init__``, replaces the fragile per-module path hack that used to
live inside the intelligence service.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
