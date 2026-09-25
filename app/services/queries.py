from collections.abc import Iterable
from typing import TypeVar

from app.schemas.common import Page, PageMeta

T = TypeVar("T")


def paginate(records: Iterable[T], page: int, page_size: int) -> Page[T]:
    ordered = sorted(records, key=lambda record: (record.nome.casefold(), record.id))
    total = len(ordered)
    start = (page - 1) * page_size
    return Page(
        data=ordered[start : start + page_size],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )
