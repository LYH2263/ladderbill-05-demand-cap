import os
import tempfile

import pytest

# 必须在导入 app.* 之前指定独立数据目录，db.py 在导入时读取 DATA_DIR。
_TMP = tempfile.mkdtemp(prefix="ladderbill-test-")
os.environ.setdefault("DATA_DIR", _TMP)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
