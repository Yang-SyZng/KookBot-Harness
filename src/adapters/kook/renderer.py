import mimetypes
import logging

from khl import Message, MessageTypes

from src.i18n import Language, kook_message
from src.agent.schema import AgentResult

log = logging.getLogger(__name__)


class KookRenderer:
    """Render agent results as KOOK messages and shared artifacts."""

    def __init__(self, asset_client=None, language: Language = "CN") -> None:
        """Initialize the KOOK result renderer.

        Args:
            asset_client: Optional KOOK client used to upload generated artifacts.
            language: Language used for messages returned to KOOK users.
        """
        self._asset_client = asset_client
        self._language = language

    async def render(self, source: Message, result: AgentResult) -> None:
        """Render an agent result in response to a KOOK message.

        The textual result is sent first. Artifacts marked as safe to share are
        then uploaded and sent as image or file messages according to their MIME
        types.

        Args:
            source: Source KOOK message to reply to.
            result: Agent result containing the response text and artifacts.

        Returns:
            None.

        Raises:
            RuntimeError: If a shareable artifact is present but no asset client
                was configured.
        """
        if result.status == "failed":
            text = kook_message(self._language, "processing_failed")
        else:
            text = result.text or kook_message(self._language, "empty_result")
        await source.reply(text, type=MessageTypes.KMD)

        for artifact in result.artifacts:
            if not artifact.safe_to_share:
                continue
            if self._asset_client is None:
                raise RuntimeError("The renderer has no configured asset client.")
            try:
                url = await self._asset_client.create_asset(artifact.path)
                guessed = artifact.mime_type or mimetypes.guess_type(artifact.name)[0] or ""
                message_type = MessageTypes.IMG if guessed.startswith("image/") else MessageTypes.FILE
                await source.reply(url, type=message_type, use_quote=False)
            except Exception:
                log.exception("failed to upload artifact %s", artifact.name)
                await source.reply(
                    kook_message(
                        self._language,
                        "artifact_upload_failed",
                        name=artifact.name,
                    ),
                    type=MessageTypes.KMD,
                    use_quote=False,
                )
