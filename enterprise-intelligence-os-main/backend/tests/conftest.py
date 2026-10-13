import os
import tempfile
import uuid
from pathlib import Path


TEST_DB = Path(tempfile.gettempdir()) / f"enterprise-intelligence-tests-{uuid.uuid4().hex}.db"
os.environ["EIOS_DB_PATH"] = str(TEST_DB)


def pytest_sessionfinish() -> None:
    for path in (TEST_DB, Path(f"{TEST_DB}-wal"), Path(f"{TEST_DB}-shm")):
        path.unlink(missing_ok=True)
