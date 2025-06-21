from typing import Annotated, Literal

from pydantic import BaseModel, Field


class DeleteRoleCallbackData(BaseModel):
    command: Literal["deleterole"] = "deleterole"
    role: str
    requested_by: str


class ShowCommandsCallbackData(BaseModel):
    command: Literal["start__showcommands"] = "start__showcommands"
    requested_by: str


type CallbackData = Annotated[
    DeleteRoleCallbackData | ShowCommandsCallbackData,
    Field(discriminator="command"),
]
