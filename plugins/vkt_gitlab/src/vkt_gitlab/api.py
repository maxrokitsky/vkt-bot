import datetime
import json
import math
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from vkt_bot.app import bot
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.core.security import verify_password, get_password_hash
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_gitlab.repositories import GlWebhookRepository, CreateGlWebhookSchema
from vkt_gitlab.schemas import (
    GlWebhookCreate,
    GlWebhookRead,
    GlWebhookUpdate,
    GlWebhookListResponse,
)
from vkt_gitlab.models import GlWebhook


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


@gl_router.get("/webhooks", response_model=GlWebhookListResponse)
async def list_webhooks(
    session: SessionDep,
    current_user: CurrentAdminUser,
    page: int = 1,
    size: int = 10,
) -> GlWebhookListResponse:
    """List all GitLab webhooks with pagination."""
    offset = (page - 1) * size

    count_stmt = select(func.count()).select_from(GlWebhook)
    total = await session.scalar(count_stmt) or 0

    stmt = (
        select(GlWebhook)
        .options(
            selectinload(GlWebhook.chat),
            selectinload(GlWebhook.created_by),
        )
        .offset(offset)
        .limit(size)
        # .order_by(GlWebhook.created_at.desc())
    )
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    items = [
        GlWebhookRead(
            id=webhook.id,
            name=webhook.name,
            chat_id=webhook.chat_id,
            chat_title=webhook.chat.title,
            created_by_id=webhook.created_by_id,
            created_by_name=webhook.created_by.name,
            last_used_at=webhook.last_used_at,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        )
        for webhook in webhooks
    ]

    return GlWebhookListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@gl_router.post("/webhooks", response_model=GlWebhookRead, status_code=201)
async def create_webhook(
    session: SessionDep,
    current_user: CurrentAdminUser,
    webhook_data: GlWebhookCreate,
) -> GlWebhookRead:
    """Create a new GitLab webhook."""
    hashed_secret = get_password_hash(webhook_data.secret)

    repository = GlWebhookRepository(session)
    webhook = await repository.create(
        CreateGlWebhookSchema(
            name=webhook_data.name,
            hashed_secret=hashed_secret,
            chat_id=webhook_data.chat_id,
            created_by_id=current_user.chat_user_id,
        )
    )

    await session.refresh(webhook, ["chat", "created_by"])

    return GlWebhookRead(
        id=webhook.id,
        name=webhook.name,
        chat_id=webhook.chat_id,
        chat_title=webhook.chat.title,
        created_by_id=webhook.created_by_id,
        created_by_name=webhook.created_by.name,
        last_used_at=webhook.last_used_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@gl_router.get("/webhooks/{webhook_id}", response_model=GlWebhookRead)
async def get_webhook(
    session: SessionDep,
    current_user: CurrentAdminUser,
    webhook_id: uuid.UUID,
) -> GlWebhookRead:
    """Get a specific GitLab webhook by ID."""
    repository = GlWebhookRepository(session)
    try:
        webhook = await repository.get(webhook_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Webhook not found") from err

    await session.refresh(webhook, ["chat", "created_by"])

    return GlWebhookRead(
        id=webhook.id,
        name=webhook.name,
        chat_id=webhook.chat_id,
        chat_title=webhook.chat.title,
        created_by_id=webhook.created_by_id,
        created_by_name=webhook.created_by.name,
        last_used_at=webhook.last_used_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@gl_router.patch("/webhooks/{webhook_id}", response_model=GlWebhookRead)
async def update_webhook(
    session: SessionDep,
    current_user: CurrentAdminUser,
    webhook_id: uuid.UUID,
    webhook_data: GlWebhookUpdate,
) -> GlWebhookRead:
    """Update a GitLab webhook."""
    repository = GlWebhookRepository(session)
    try:
        webhook = await repository.get(webhook_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Webhook not found") from err

    if webhook_data.name is not None:
        webhook.name = webhook_data.name

    session.add(webhook)
    await session.commit()
    await session.refresh(webhook, ["chat", "created_by"])

    return GlWebhookRead(
        id=webhook.id,
        name=webhook.name,
        chat_id=webhook.chat_id,
        chat_title=webhook.chat.title,
        created_by_id=webhook.created_by_id,
        created_by_name=webhook.created_by.name,
        last_used_at=webhook.last_used_at,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
    )


@gl_router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    session: SessionDep,
    current_user: CurrentAdminUser,
    webhook_id: uuid.UUID,
) -> None:
    """Delete a GitLab webhook."""
    repository = GlWebhookRepository(session)
    try:
        webhook = await repository.get(webhook_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Webhook not found") from err

    await session.delete(webhook)
    await session.commit()


@gl_router.post("/webhooks/{webhook_id}/trigger", response_model=None)
async def trigger_webhook(
    session: SessionDep,
    webhook_id: uuid.UUID,
    x_gitlab_token: Annotated[str, Header()],
    x_gitlab_event: Annotated[str, Header()],
    data: dict[str, Any],
) -> Any:
    """GitLab webhook trigger endpoint."""
    if x_gitlab_event not in ("Pipeline Hook",):
        return None

    repository = GlWebhookRepository(session)
    try:
        webhook = await repository.get(webhook_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Webhook not found") from err

    if not verify_password(x_gitlab_token, webhook.hashed_secret):
        raise HTTPException(status_code=403, detail="Invalid token")

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

    if data["object_attributes"]["status"] not in ["failed", "success"]:
        return

    await bot.send_text(
        webhook.chat_id,
        construct_messsage(data),
        parse_mode="MarkdownV2",
        inline_keyboard_markup=kb,
    )
