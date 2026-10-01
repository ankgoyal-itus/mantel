"""Loaded by pytest before anything under tests/, and before mantel_api.app.

The app module builds an app on import, and that app opens content/ and the
ledger wherever paths.py says they are. So the whole session is pointed at a
MANTEL_HOME of its own, rendered from content.sample/ — the fictional family —
before any test module can import it. A test that reads "the real plan" reads
the sample; nothing a test does can touch the family's own files.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

from mantel_api.sample import make_home

SESSION = Path(tempfile.mkdtemp(prefix="mantel-tests-"))
make_home(SESSION / "home", date.today())
os.environ["MANTEL_HOME"] = str(SESSION / "home")
os.environ.pop("MANTEL_CONTENT_DIR", None)
os.environ.pop("MANTEL_DB_PATH", None)
atexit.register(shutil.rmtree, SESSION, ignore_errors=True)
