from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    results: list[T]
    page: int
    total: int
