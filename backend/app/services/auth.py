"""用户认证服务：口令哈希、token 签发与解析、登录态依赖。

口径见 `docs/3_接口契约文档.md`「用户认证约定」（2026-10）与 `docs/2_数据库设计.md` §2.4：

- 用户名：字符集为中文 / 字母 / 数字 / 下划线（不含空格），长度按 **UTF-8 字节** 计 3~20
  （中文 1 字 = 3 字节，故 1~6 个汉字；纯 ASCII 名与前端「3~20 字符」完全一致）。
- 密码：6~20 位，服务端加盐哈希存储，任何接口都不返回密码相关字段。
- token：`secrets.token_hex(32)`（64 字符）存 `users.token`，有效期 7 天；**新登录顶掉旧 token**
  （单设备在线），过期或换 token 后旧 token 立即失效。
- 哈希算法：标准库 `pbkdf2_hmac('sha256')`（无第三方依赖，避免 passlib/bcrypt 的版本兼容坑），
  存储格式 `pbkdf2_sha256$<迭代次数>$<salt hex>$<hash hex>`，校验用 `hmac.compare_digest` 恒时比较。
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

TOKEN_TTL_DAYS = 7
USERNAME_MIN_BYTES, USERNAME_MAX_BYTES = 3, 20
PASSWORD_MIN, PASSWORD_MAX = 6, 20

_PBKDF2_ROUNDS = 200_000
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]+$")
# 中文常用区 + 扩展A，覆盖绝大多数中文昵称
_USERNAME_HINT = "用户名需 3~20 个字符（中文、字母、数字、下划线，不含空格）"


# ============================ 校验与哈希 ============================


def validate_username(username: str) -> str | None:
    """返回错误文案；None 表示通过。"""
    if not _USERNAME_RE.match(username):
        return _USERNAME_HINT
    if not (USERNAME_MIN_BYTES <= len(username.encode("utf-8")) <= USERNAME_MAX_BYTES):
        return _USERNAME_HINT
    return None


def validate_password(password: str) -> str | None:
    """返回错误文案；None 表示通过。"""
    if not (PASSWORD_MIN <= len(password) <= PASSWORD_MAX):
        return f"密码需 {PASSWORD_MIN}~{PASSWORD_MAX} 位"
    return None


def hash_password(password: str) -> str:
    """加盐哈希（每次调用 salt 不同，同一密码两次结果不同）。"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """恒时校验；哈希格式非法一律视为不匹配（不抛异常）。"""
    try:
        algo, rounds, salt, expected = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False


def new_token() -> str:
    """64 字符 token（对应 users.token String(64)）。"""
    return secrets.token_hex(32)


def issue_token(user: models.User) -> str:
    """签发新 token 并顶掉旧 token（调用方负责 commit）。"""
    user.token = new_token()
    user.token_expires_at = datetime.utcnow() + timedelta(days=TOKEN_TTL_DAYS)
    return user.token


# ============================ 登录态解析 ============================


def _extract_token(authorization: str | None) -> str | None:
    """从 `Authorization: Bearer <token>` 取 token；格式不对返回 None。"""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def resolve_user(db: Session, authorization: str | None) -> models.User | None:
    """按 token 反查用户；无 token / token 不存在 / 已过期 一律返回 None（不抛异常）。"""
    token = _extract_token(authorization)
    if token is None:
        return None
    user = db.query(models.User).filter(models.User.token == token).first()
    if user is None:
        return None
    if user.token_expires_at is not None and user.token_expires_at < datetime.utcnow():
        return None       # 有过期时间且已过期；无过期时间（历史/测试数据）按有效处理
    return user


# ============================ FastAPI 依赖 ============================


def optional_user(authorization: str | None = Header(default=None),
                  db: Session = Depends(get_db)) -> models.User | None:
    """可选登录态：/crawl、/recommend 用。未登录/失效按游客处理，绝不报 401。"""
    return resolve_user(db, authorization)


def optional_user_id(user: models.User | None = Depends(optional_user)) -> int | None:
    return user.id if user is not None else None


def current_user(authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db)) -> models.User:
    """/auth/me、/auth/logout 用：强制登录态，缺失/失效/过期一律 401。"""
    user = resolve_user(db, authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return user
