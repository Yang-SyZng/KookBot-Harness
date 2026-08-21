from agents import set_tracing_disabled
from khl import Bot, Message

from src.adapters.kook.attachments import AttachmentDownloader
from src.adapters.kook.ingress import KookIngress
from src.adapters.kook.normalizer import KookNormalizer
from src.adapters.kook.renderer import KookRenderer
from src.agent.bridge import AgentBridge
from src.agent.service import AgentService
from src.config import AppSettings
from src.runtime.dedupe import MessageDeduplicator


def build_bot(settings: AppSettings | None = None) -> Bot:
    """Build and configure the KOOK bot.

    Args:
        settings: Optional application settings. If omitted, settings are loaded
            from the environment.

    Returns:
        The configured KOOK bot instance.
    """
    settings = settings or AppSettings()

    bot = Bot(token=settings.kook_token.get_secret_value())
    normalizer = KookNormalizer(bot)

    bridge = AgentBridge(AgentService(settings), language=settings.language)

    renderer = KookRenderer(bot.client, language=settings.language)

    downloader = AttachmentDownloader(max_bytes=settings.max_attachment_bytes)
    dedupe = MessageDeduplicator(settings.workspace_root / ".dedupe")

    ingress = KookIngress(
        normalizer=normalizer,
        bridge=bridge,
        renderer=renderer,
        downloader=downloader,
        dedupe=dedupe,
        workspace_root=settings.workspace_root,
        language=settings.language,
    )

    set_tracing_disabled(True)

    @bot.on_message()
    async def receive(msg: Message) -> None:
        """Forward an incoming KOOK message to the ingress handler.

        Args:
            msg: Incoming KOOK message.
        """
        await ingress.handle(msg)

    return bot


def run() -> None:
    """Build and run the KOOK bot."""
    build_bot().run()
