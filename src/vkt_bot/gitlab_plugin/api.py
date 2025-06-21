import datetime
import json
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, HTTPException, Header

from vkt_bot.teams_bot.app import bot
from vkt_bot.bot_framework.exceptions import NotFoundError
from vkt_bot.core.security import verify_password
from vkt_bot.gitlab_plugin.repositories import GlWebhookRepository
from vkt_bot.webapp.db import DB

gl_router = APIRouter(prefix="/gl", tags=["gitlab"])


success_message = """✅ Пайплайн прошёл • 🦊 [{project_name}]({project_url}) • `{branch}` • [{sha}]({commit_url})
> {message}
>👤 {author}"""

fail_message = """❌ Пайплайн упал • 🦊 [{project_name}]({project_url}) • `{branch}` • [{sha}]({commit_url})
> {message}
>👤 {author}"""


def construct_messsage(data: dict[str, Any]) -> str:
    template = (
        success_message
        if data["object_attributes"]["status"] == "success"
        else fail_message
    )
    return template.format(
        project_name=data["project"]["path_with_namespace"],
        project_url=data["project"]["web_url"],
        branch=data["object_attributes"]["ref"],
        message=data["commit"]["message"].split("\n", 1)[0][:160],
        author=data["user"]["username"],
        pipeline_url=data["object_attributes"]["url"],
        sha=data["object_attributes"]["sha"][:8],
        commit_url=data["commit"]["url"],
    )


@gl_router.post("/webhooks/{webhook_id}", response_model=None)
async def trigger_webhook(
    session: DB,
    webhook_id: uuid.UUID,
    x_gitlab_token: Annotated[str, Header()],
    x_gitlab_event: Annotated[str, Header()],
    data: dict[str, Any],
) -> Any:
    """Вебхук."""
    if x_gitlab_event not in ("Pipeline Hook",):
        return None

    repository = GlWebhookRepository(session)
    try:
        webhook = await repository.get(webhook_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Вебхук не найден") from err

    if not verify_password(x_gitlab_token, webhook.hashed_secret):
        return None
    kb = json.dumps(
        [
            [
                {"text": "Открыть", "url": data["object_attributes"]["url"]},
            ]
        ],
        ensure_ascii=False,
    )

    webhook.last_used_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(webhook)
    await session.commit()

    await bot.send_text(
        webhook.chat_id,
        construct_messsage(data),
        parse_mode="MarkdownV2",
        inline_keyboard_markup=kb,
    )
