from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vkt_bot import setup

from .api import auth, users, chats, roles, chat_users

app = FastAPI(title="VKT Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(roles.router)
app.include_router(chat_users.router)


@app.get("/")
async def root():
    return {"message": "VKT Bot API"}


@app.get("/health")
async def health():
    return {"status": "ok"}


def setup_app():
    setup()
    return app