import logging
from pathlib import Path
from src.ver import version

from khl import Message

from src.agent.schema import AgentRequest, AgentResult
from src.runtime.workspace import task_workspace
from src.adapters.kook.normalizer import KookNormalizer
from src.adapters.kook.renderer import KookRenderer
from src.adapters.kook.attachments import AttachmentDownloader
from src.runtime.dedupe import MessageDeduplicator
from src.agent.bridge import AgentBridge
from src.i18n import Language, kook_message

log = logging.getLogger(__name__)


class KookIngress:
    """Coordinate incoming KOOK message processing."""

    def __init__(
                self, *, 
                normalizer: KookNormalizer, 
                bridge: AgentBridge, 
                renderer: KookRenderer, 
                downloader: AttachmentDownloader, 
                dedupe: MessageDeduplicator,
                workspace_root: Path,
                language: Language = "CN",
    ) -> None:
        """Initialize the KOOK message ingress handler.

        Args:
            normalizer: Normalizer used to convert KOOK messages into internal
                message models.
            bridge: Bridge used to submit requests to the agent service.
            renderer: Renderer used to send agent results back to KOOK.
            downloader: Downloader used to store message attachments locally.
            dedupe: Deduplicator used to prevent repeated message processing.
            workspace_root: Root directory for task-specific workspaces.
            language: Language used for messages returned to KOOK users.
        """
        self._normalizer = normalizer
        self._bridge = bridge
        self._renderer = renderer
        self._downloader = downloader
        self._dedupe = dedupe
        self._workspace_root = workspace_root
        self._language = language

    async def handle(self, msg: Message) -> None:
        """Process an incoming KOOK message.

        The message is normalized, deduplicated, processed by the agent, and
        rendered back to KOOK. Processing failures are converted into failed agent
        results and sent to the user.

        Args:
            msg: Incoming KOOK message.

        Returns:
            None.
        """
        incoming = await self._normalizer.normalize(msg)

        if incoming is None or not self._dedupe.claim(incoming.message_id):
            return

        try:
            # create workspace
            workspace = task_workspace(
                self._workspace_root, incoming.user_id, incoming.message_id
            )
            if len(incoming.attachments) > 1:
                result = AgentResult(
                    text=kook_message(
                        self._language,
                        "too_many_attachments",
                        version=version,
                    ),
                    status="waiting_user",
                )
            else:
                file_path = None
                if incoming.attachments:
                    file_path = await self._downloader.download_one(
                        incoming.attachments[0], workspace
                    )
                result = await self._bridge.run(AgentRequest(
                    request_id=incoming.message_id,
                    user_id=incoming.user_id,
                    channel_id=incoming.channel_id,
                    text=incoming.text,
                    file_path=file_path,
                    workspace=workspace,
                ))
            await self._renderer.render(msg, result)
            self._dedupe.mark(incoming.message_id, "completed")
        except Exception as exc:
            log.exception("message processing failed: %s", incoming.message_id)
            self._dedupe.mark(incoming.message_id, "failed")
            await self._renderer.render(
                msg, AgentResult(status="failed", error=str(exc))
            )
