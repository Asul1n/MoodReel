"""数据库引擎与会话（SQLite，表结构见 models.py，对应规格 §4 数据模型）。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},  # FastAPI 线程池中复用连接
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """启动时建表（models 里注册的 Base.metadata）。"""
    from . import models  # noqa: F401  确保表被注册

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
