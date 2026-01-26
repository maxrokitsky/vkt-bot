from pydantic import BaseModel, ConfigDict, computed_field

from vkt_bot.config import settings


class UserResponse(BaseModel):
    id: str
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_owner(self) -> bool:
        """Check if this user is the owner."""
        return settings.owner_id is not None and self.id == settings.owner_id
