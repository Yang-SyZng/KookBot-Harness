import mimetypes
from pathlib import Path

from src.artifacts.store import ArtifactStore


ALLOWED_TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv"}


class TaskFileTools:
    """Provide safe input-reading and artifact-writing tools for a task."""

    def __init__(
        self,
        workspace: Path,
        file_path: Path | None = None,
        max_artifact_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        """Initialize file tools for a task workspace.

        Args:
            workspace: Workspace containing the task input and output directories.
            file_path: Optional path to the task's input file.
            max_artifact_bytes: Maximum allowed size of a generated artifact in
                bytes.

        Raises:
            ValueError: If the input file is outside the task's input directory or
                is not a regular file.
        """
        self.workspace = workspace.resolve()
        self.file_path = file_path.resolve() if file_path else None
        self.max_artifact_bytes = max_artifact_bytes
        self.store = ArtifactStore(self.workspace, max_artifact_bytes)

        if self.file_path is not None:
            input_dir = self.workspace / "input"
            if self.file_path.parent != input_dir or not self.file_path.is_file():
                raise ValueError("The input file does not belong to the current task.")

    def read_input(self) -> str:
        """Read the task's input file when it is a supported text format.

        Returns:
            The input text, truncated to 200,000 characters, or a user-facing
            message if no readable input file is available.
        """
        if self.file_path is None:
            return "[Warnning] The current task has no input file."
        if self.file_path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
            return f"[Error] Currently, The {self.file_path.suffix or 'Uknow'} format is not supported for reading."
        return self.file_path.read_text(encoding="utf-8")[:200_000]

    def write_artifact(self, name: str, content: str) -> str:
        """Write and register a text artifact in the task workspace.

        Args:
            name: Safe filename with a supported text-file extension.
            content: Complete text content of the artifact.

        Returns:
            A user-facing message indicating whether the artifact was registered
            or rejected.
        """
        safe_name = Path(name).name
        suffix = Path(safe_name).suffix.lower()
        if safe_name != name or suffix not in ALLOWED_TEXT_SUFFIXES:
            return "[Rejection] Only allow file names of the formats .txt/.md/.json/.csv that are safe."
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_artifact_bytes:
            return "[Rejection] Product exceeds size limit"
        path = self.workspace / "output" / safe_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        artifact = self.store.register(
            path,
            name=safe_name,
            mime_type=mimetypes.guess_type(safe_name)[0] or "text/plain",
            safe_to_share=True,
        )
        return f"Registered artifact: {artifact.name}"
