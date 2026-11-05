import math
from typing import TypeVar, Generic, List
from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T
    message: str = "success"


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    page_size: int
    pages: int
    message: str = "success"

    @classmethod
    def build(cls, items: list, total: int, page: int, page_size: int):
        return cls(
            data=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if page_size else 1,
        )


class MessageResponse(BaseModel):
    message: str
