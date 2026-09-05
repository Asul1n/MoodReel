"""数据库引擎与会话（SQLite，表结构见 models.py，对应规格 §4 数据模型）。"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},  # FastAPI 线程池中复用连接
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# 老库自动补列（models.py 若加了可空新列，在下方对应表登记即可，启动时 ALTER 补上）
_COLUMNS_BY_TABLE = {
    "movies": {
        "intro": "TEXT",
        "poster": "VARCHAR(500)",
        "rating": "FLOAT",
        "genres": "VARCHAR(200)",
    },
    "reviews": {
        "review_time": "VARCHAR(32)",
    },
    "crawl_jobs": {
        "refresh": "BOOLEAN",
    },
}


def _migrate() -> None:
    """对已存在的表补新增的可空列（新建表由 create_all 覆盖）。"""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _COLUMNS_BY_TABLE.items():
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, typ in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))


def init_db() -> None:
    """启动时建表（models 里注册的 Base.metadata）+ 老库迁移。"""
    from . import models  # noqa: F401  确保表被注册

    Base.metadata.create_all(bind=engine)
    _migrate()


def get_db():
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
