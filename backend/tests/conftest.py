"""pytest 全局配置：把 backend/ 加入 sys.path，DB 指到临时文件。

运行：cd backend && pytest -q
"""
import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP = pathlib.Path(__file__).parent / "_tmp_test"
_TMP.mkdir(exist_ok=True)
os.environ["MOODREEL_DB"] = str(_TMP / "test.db")
