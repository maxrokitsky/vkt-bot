
from fastapi import FastAPI

from .controllers.role import roles_router
from .controllers.chat import chat_router
from .controllers.user import user_router

app = FastAPI()


app.include_router(roles_router)
app.include_router(chat_router)
app.include_router(user_router)
