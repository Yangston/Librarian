"""Common API response schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Consistent JSON envelope for API responses."""

    data: T

