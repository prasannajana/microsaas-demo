"""Schemas shared across modules."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A page of results: `items` plus pagination metadata."""

    items: list[T]
    total: int
    page: int
    size: int
