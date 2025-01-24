
from fastapi import FastAPI

from .controllers.role import roles_router

app = FastAPI()


app.include_router(roles_router)
