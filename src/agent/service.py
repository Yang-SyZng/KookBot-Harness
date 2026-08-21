from pathlib import Path

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, function_tool
from openai import AsyncOpenAI

from src.agent.file_tools import TaskFileTools
from src.config import AppSettings
from src.models import AgentResult


class AgentService:
    """Configure and run the agent with task-specific file tools."""

    def __init__(
        self,
        settings: AppSettings,
        runner=Runner,
        agent: Agent | None = None,
    ) -> None:
        """Initialize the agent service.

        Args:
            settings: Application settings containing the model connection details,
                thinking parameters, and artifact size limit.
            runner: Runner used to execute the agent. Defaults to ``Runner``.
            agent: Optional custom agent. If omitted, a default agent is created
                from the application settings.
        """
        # Default
        if agent is None:
            client = AsyncOpenAI(
                api_key=settings.api_key.get_secret_value(),
                base_url=str(settings.base_url),
            )

            model = OpenAIChatCompletionsModel(
                model=settings.llm_model_id,
                openai_client=client,
            )
            extra_body = None
            if settings.agent_think_enabled is not None:
                extra_body = {settings.think_parameter: settings.agent_think_enabled}

            # Create the default KOOK agent.
            agent = Agent(
                name="KookAgent",
                instructions=(
                    "你是 KOOK 中的中文 Agent。回答应简洁可操作。"
                    "有输入文件时先用 read_input_file 读取。"
                    "只在用户明确要求生成文件时使用 write_artifact。"
                ),
                model=model,
                model_settings=ModelSettings(extra_body=extra_body),
            )

        # Store the agent, runner, and artifact size limit.
        self._agent = agent
        self._runner = runner
        self._max_artifact_bytes = settings.max_artifact_bytes

    async def run(
        self,
        user_input: str,
        file_path: Path | None = None,
        workspace: Path | None = None,
    ) -> AgentResult:
        """Run the agent and return its response and generated artifacts.

        Args:
            user_input: Task content provided by the user.
            file_path: Path to the user-uploaded file, or ``None`` if no file was
                uploaded.
            workspace: Working directory used to read input files and store
                generated artifacts.

        Returns:
            The agent result containing the final text, artifact list, and
            completion status.

        Raises:
            ValueError: If an input file is provided without a task workspace.
        """
        tools = []
        file_tools = (
            TaskFileTools(workspace, file_path, self._max_artifact_bytes)
            if workspace else None
        )
        store = file_tools.store if file_tools else None

        if file_path is not None:
            if workspace is None:
                raise ValueError(
                    "A task workspace is required when an input file is provided."
                )

            @function_tool
            def read_input_file() -> str:
                """Read the single text file uploaded by the user.

                Returns:
                    The text content of the input file.
                """
                return file_tools.read_input()

            tools.append(read_input_file)

        if store is not None:
            @function_tool
            def write_artifact(name: str, content: str) -> str:
                """Create and register a text artifact for the current task.

                Args:
                    name: Safe filename with a .txt, .md, .json, or .csv extension.
                    content: Complete content to write to the file.

                Returns:
                    Registration information for the generated artifact.
                """
                return file_tools.write_artifact(name, content)

            tools.append(write_artifact)

        run_agent = self._agent.clone(tools=tools)
        result = await self._runner.run(run_agent, user_input)
        return AgentResult(
            text=str(result.final_output) if result.final_output is not None else None,
            artifacts=store.list() if store else [],
            status="completed",
        )
