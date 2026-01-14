from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: str
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)
