from fastapi import FastAPI

from .api.auth import auth_router
from .api.chat import chat_router
from .api.chat_user import chat_user_router
from .api.role import roles_router
from .api.user import user_router
from gitlab_plugin.api import gl_router

app = FastAPI()


app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(chat_router)
app.include_router(user_router)
app.include_router(chat_user_router)
app.include_router(gl_router)
