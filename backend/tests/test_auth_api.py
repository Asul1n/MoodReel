"""用户认证接口测试（接口契约「用户认证约定」2026-10）。

口径：注册 201/409/400；登录 200/401，新登录顶掉旧 token；/auth/me 与
/auth/logout 校验 Bearer token，无效/过期 401；任何接口不返回密码字段。
"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def _register(username="小明", password="pass123"):
    return client.post("/auth/register",
                       json={"username": username, "password": password})


def test_register_creates_user_201() -> None:
    r = _register()
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "小明"
    assert body["user_id"]
    assert body["created_at"]

    db = SessionLocal()
    try:
        u = db.get(models.User, body["user_id"])
        assert u is not None
        assert u.password_hash != "pass123"          # 绝不存明文
        assert u.password_hash != u.password_hash.lower() or "$" in u.password_hash
    finally:
        db.close()


def test_register_duplicate_username_409() -> None:
    assert _register().status_code == 201
    r = _register(password="other66")
    assert r.status_code == 409
    assert r.json()["detail"] == "用户名已存在"


def test_register_rejects_bad_username() -> None:
    assert _register(username="ab").status_code == 400            # 太短
    assert _register(username="a" * 21).status_code == 400        # 太长
    assert _register(username="有 空格名").status_code == 400      # 含空格
    assert _register(username="bad!name").status_code == 400      # 非法字符


def test_register_rejects_bad_password() -> None:
    assert _register(password="12345").status_code == 400         # <6 位
    assert _register(password="p" * 21).status_code == 400        # >20 位


def test_login_returns_token() -> None:
    _register()
    r = client.post("/auth/login", json={"username": "小明", "password": "pass123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"]["username"] == "小明"
    assert "password" not in str(body)

    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username="小明").first()
        assert u.token == body["token"]
        assert u.token_expires_at > datetime.utcnow() + timedelta(days=6)
    finally:
        db.close()


def test_login_wrong_credentials_401() -> None:
    _register()
    r = client.post("/auth/login", json={"username": "小明", "password": "wrong!"})
    assert r.status_code == 401
    assert r.json()["detail"] == "用户名或密码错误"
    r = client.post("/auth/login", json={"username": "不存在", "password": "pass123"})
    assert r.status_code == 401


def test_login_replaces_old_token() -> None:
    """新登录顶掉旧 token（单设备在线）。"""
    _register()
    t1 = client.post("/auth/login", json={"username": "小明", "password": "pass123"}).json()["token"]
    t2 = client.post("/auth/login", json={"username": "小明", "password": "pass123"}).json()["token"]
    assert t1 != t2

    me1 = client.get("/auth/me", headers={"Authorization": f"Bearer {t1}"})
    assert me1.status_code == 401                    # 旧 token 失效
    me2 = client.get("/auth/me", headers={"Authorization": f"Bearer {t2}"})
    assert me2.status_code == 200


def test_me_returns_user_info() -> None:
    uid = _register().json()["user_id"]
    token = client.post("/auth/login", json={"username": "小明", "password": "pass123"}).json()["token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == uid
    assert body["username"] == "小明"


def test_me_rejects_missing_or_bad_token() -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer deadbeef"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_me_rejects_expired_token() -> None:
    _register()
    token = client.post("/auth/login", json={"username": "小明", "password": "pass123"}).json()["token"]
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(username="小明").first()
        u.token_expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_logout_clears_token() -> None:
    _register()
    token = client.post("/auth/login", json={"username": "小明", "password": "pass123"}).json()["token"]
    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
