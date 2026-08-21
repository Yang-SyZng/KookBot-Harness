import re
import json
from datetime import datetime, timezone

from khl import Bot, Message, MessageTypes

from src.models import Attachment, IncomingMessage


class KookNormalizer:
    """Convert KOOK messages into the application's internal message model."""

    def __init__(self, bot: Bot) -> None:
        """Initialize the KOOK message normalizer.

        Args:
            bot: KOOK bot used to identify the current bot account and access its
                API client.
        """
        self._bot = bot

    async def normalize(self, msg: Message) -> IncomingMessage | None:
        """Normalize an incoming KOOK message.

        Messages sent by bots, messages that do not mention the current bot, and
        malformed card messages are ignored.

        Args:
            msg: Incoming KOOK message to normalize.

        Returns:
            The normalized internal message, or ``None`` if the message should be
            ignored.
        """
        # Skip the robot itself
        bot_user = await self._bot.client.fetch_me()
        if getattr(msg.author, "bot", False) or msg.author_id == bot_user.id:
            return None
        if bot_user.id not in (msg.extra.get("mention") or []):
            return None

        text = msg.content or ""
        attachments = []

        # type of message
        if msg.type == MessageTypes.KMD:
            text = (msg.extra.get("kmarkdown") or {}).get("raw_content") or text
        elif msg.type == MessageTypes.CARD:
            text_parts = []
            try:
                cards = json.loads(text)
            except (TypeError, json.JSONDecodeError):
                return None
            for card in cards:
                for module in card.get("modules", []):
                    module_type = module.get("type")
                    if module_type == "section":
                        content = (module.get("text") or {}).get("content")
                        if content:
                            text_parts.append(content)
                        accessory = module.get("accessory") or {}
                        if accessory.get("type") == "image" and accessory.get("src"):
                            attachments.append(Attachment(
                                url=accessory["src"], name=accessory.get("alt"), kind="image"
                            ))
                    elif module_type in {"container", "image-group", "context"}:
                        for element in module.get("elements", []):
                            url = element.get("src")
                            if url:
                                attachments.append(Attachment(
                                    url=url,
                                    name=element.get("title") or element.get("name"),
                                    mime_type=element.get("mime_type"),
                                    kind="image" if element.get("type") == "image" else "file",
                                ))
                    elif module_type in {"file", "audio", "video"} and module.get("src"):
                        attachments.append(Attachment(
                            url=module["src"],
                            name=module.get("title"),
                            mime_type=module.get("mime_type"),
                            kind=module_type,
                        ))
            text = "\n".join(text_parts)
        text = re.sub(rf"\(met\){re.escape(bot_user.id)}\(met\)", "", text)
        text = re.sub(rf"<@!?{re.escape(bot_user.id)}>", "", text).strip()

        guild = getattr(getattr(msg, "ctx", None), "guild", None)
        timestamp = getattr(msg, "msg_timestamp", None)
        received_at = datetime.now(timezone.utc)
        if timestamp:
            received_at = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)

        return IncomingMessage(
            message_id=msg.id,
            server_id=getattr(guild, "id", None),
            channel_id=msg.channel.id,
            user_id=msg.author_id,
            text=text or None,
            attachments=attachments,
            received_at=received_at,
        )
