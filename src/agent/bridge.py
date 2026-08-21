from typing import Protocol

from src.i18n import Language, kook_message
from src.models import AgentRequest, AgentResult


class AgentServicePort(Protocol):
    """Define the interface required for an agent service."""

    async def run(
        self,
        user_input: str,
        file_path: str | None = None,
        workspace: str | None = None,
    ) -> AgentResult:
        """Run the agent service for a user request.

        Args:
            user_input: User-provided instructions for the agent.
            file_path: Optional path to the input file.
            workspace: Optional task workspace path.

        Returns:
            The result produced by the agent service.
        """
        ...


class AgentBridge:
    """Validate agent requests and forward them to the agent service."""

    def __init__(
        self,
        agent_service: AgentServicePort,
        language: Language = "CN",
    ) -> None:
        """Initialize the bridge with an agent service.

        Args:
            agent_service: Service used to execute validated agent requests.
            language: Language used for messages returned to KOOK users.
        """
        # Store the service dependency used to execute valid agent requests.
        self._agent_service = agent_service
        self._language = language

    async def run(self, request: AgentRequest) -> AgentResult:
        """Validate and process an agent request.

        Requests without text are handled locally. Valid requests are forwarded to
        the agent service, and service exceptions are converted into failed
        results.

        Args:
            request: Agent request to validate and process.

        Returns:
            The resulting agent state.
        """

        # Reject requests that contain neither text nor an attached file.
        if not request.text and request.file_path is None:
            return AgentResult(
                status="failed",
                error="There is no content in the message.",
            )

        # Ask the user for instructions when only a file is provided.
        if not request.text and request.file_path is not None:
            return AgentResult(
                text=kook_message(self._language, "file_instructions_required"),
                status="waiting_user",
            )

        try:
            # Forward the validated request to the underlying agent service.
            return await self._agent_service.run(
                user_input=request.text or "",
                file_path=request.file_path,
                workspace=request.workspace,
            )
        except Exception as exc:
            # Convert unexpected service errors into a consistent failure result.
            return AgentResult(status="failed", error=str(exc))
