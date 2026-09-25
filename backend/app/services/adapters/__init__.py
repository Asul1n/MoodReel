"""适配器注册表。

v1 目标站点为 bangumi / bilibili（规格 §3.3）。
各适配器模块在文件末尾 import 以触发 @register 登记；
尚未实现的站点 get_adapter() 返回 None，调用方据此如实上报。
"""
from .base import (AnimeReview, Candidate, Meta, Rating, SourceAdapter,
                   SourceResult, degraded, failed, ok)

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """类装饰器：把适配器登记进注册表。"""
    _REGISTRY[cls.source] = cls
    return cls


def get_adapter(source: str):
    """按站点名取适配器实例；未实现返回 None。"""
    if source not in _REGISTRY:
        return None
    return _REGISTRY[source]()


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


# 各站点适配器在实现后于此处 import 触发注册（Task 3 / Task 4）
# from . import bangumi as _bangumi    # noqa: E402,F401
# from . import bilibili as _bilibili  # noqa: E402,F401
