"""用户认证路由：注册 / 登录 / 当前用户 / 退出登录。

契约见 `docs/3_接口契约文档.md`「用户认证约定」（2026-10）：
- `POST /auth/register` 201 → `{user_id, username, created_at}`；用户名重复 409；校验失败 400
- `POST /auth/login`    200 → `{token, user:{user_id, username}}`；凭据错误 401（新登录顶掉旧 token）
- `GET  /auth/me`       200 → `{user_id, username, created_at}`；token 缺失/失效/过期 401
- `POST /auth/logout`   200 → `{ok: true}`；清空 token 使旧 token 立即失效
- 任何接口都不返回 password 相关字段。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..schemas import (AuthUserOut, LoginOut, LogoutOut, RegisterIn,
                       RegisterOut)
from ..services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _validate(payload: RegisterIn) -> None:
    """统一入参校验（错误 400，文案与前端提示一致）。"""
    username = (payload.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    err = auth.validate_username(username) or auth.validate_password(payload.password or "")
    if err:
        raise HTTPException(status_code=400, detail=err)


@router.post("/register", response_model=RegisterOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    _validate(payload)
    username = payload.username.strip()

    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = models.User(username=username,
                       password_hash=auth.hash_password(payload.password),
                       created_at=datetime.utcnow())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:      # 并发注册同一用户名，唯一索引兜底
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在")
    db.refresh(user)
    return RegisterOut(user_id=user.id, username=user.username,
                       created_at=user.created_at)


@router.post("/login", response_model=LoginOut)
def login(payload: RegisterIn, db: Session = Depends(get_db)) -> LoginOut:
    username = (payload.username or "").strip()
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None or not auth.verify_password(payload.password or "", user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = auth.issue_token(user)      # 顶掉旧 token（单设备在线）
    db.commit()
    return LoginOut(token=token, user=AuthUserOut(user_id=user.id, username=user.username))


@router.get("/me", response_model=RegisterOut)
def me(user: models.User = Depends(auth.current_user)) -> RegisterOut:
    return RegisterOut(user_id=user.id, username=user.username,
                       created_at=user.created_at)


@router.post("/logout", response_model=LogoutOut)
def logout(user: models.User = Depends(auth.current_user),
           db: Session = Depends(get_db)) -> LogoutOut:
    user.token = None
    user.token_expires_at = None
    db.commit()
    return LogoutOut()
