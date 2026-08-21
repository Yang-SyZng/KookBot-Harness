from khl import Bot, Message

from src.adapters.kook.normalizer import KookNormalizer
from src.models import IncomingMessage


async def captureMSG(bot: Bot, msg: Message) -> IncomingMessage | None:
    """Normalize a KOOK message through the backward-compatible entry point.

    Args:
        bot: KOOK bot associated with the incoming message.
        msg: Incoming KOOK message to normalize.

    Returns:
        The normalized message, or ``None`` if the message should be ignored.
    """
    return await KookNormalizer(bot).normalize(msg)
