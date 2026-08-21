from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Describe a file or media attachment received from KOOK."""

    url: str
    name: str | None = None
    mime_type: str | None = None
    kind: Literal["image", "file", "audio", "video"]


class IncomingMessage(BaseModel):
    """Represent a normalized message received from KOOK."""

    schema_ver: str = "v1"

    message_id: str
    server_id: str | None = None
    channel_id: str
    user_id: str
    text: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

__all__ = ["AgentRequest", "AgentResult", "Artifact", "Attachment", "IncomingMessage"]
