"""pytest 全局配置：把 backend/ 加入 sys.path，DB 指到临时文件，每用例重建表。

运行：cd backend && pytest -q
"""
import os
import pathlib
import sys

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP = pathlib.Path(__file__).parent / "_tmp_test"
_TMP.mkdir(exist_ok=True)
os.environ["MOODREEL_DB"] = str(_TMP / "test.db")

from app.db import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401  确保表已注册


@pytest.fixture(autouse=True)
def _clean_db():
    """每个用例独立空库，避免用例间数据污染。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
