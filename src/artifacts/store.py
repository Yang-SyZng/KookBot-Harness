import json
from pathlib import Path

from src.models import Artifact


class ArtifactStore:
    """Register and track artifacts generated in a task workspace."""

    def __init__(
        self,
        workspace: Path,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        """Initialize the artifact store.

        Args:
            workspace: Task workspace containing the artifact output directory.
            max_bytes: Maximum allowed size of each artifact in bytes.
        """
        self._workspace = workspace.resolve()
        self._output = self._workspace / "output"
        self._output.mkdir(parents=True, exist_ok=True)
        self._manifest = self._workspace / "artifacts.json"
        self._max_bytes = max_bytes
        self._artifacts: list[Artifact] = []

    def register(
        self,
        path: Path,
        *,
        name: str,
        mime_type: str,
        safe_to_share: bool = False,
    ) -> Artifact:
        """Validate, register, and persist metadata for an artifact.

        Args:
            path: Path to the artifact file in the workspace output directory.
            name: Safe filename used to identify the artifact.
            mime_type: MIME type of the artifact.
            safe_to_share: Whether the artifact may be shared with the user.

        Returns:
            The registered artifact metadata.

        Raises:
            ValueError: If the artifact does not exist, is outside the output
                directory, has an unsafe name, or exceeds the size limit.
        """
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError("The artifact file does not exist.")
        if resolved.parent != self._output:
            raise ValueError("The artifact file must be placed in the 'output' directory of the current task.")
        safe_name = Path(name).name
        if safe_name != name or not safe_name:
            raise ValueError("Artifact name is not safe")
        if resolved.stat().st_size > self._max_bytes:
            raise ValueError("The artifact exceeds the size limit.")

        artifact = Artifact(
            path=resolved,
            name=safe_name,
            mime_type=mime_type,
            safe_to_share=safe_to_share,
        )
        self._artifacts.append(artifact)
        temporary = self._manifest.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in self._artifacts],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self._manifest)
        return artifact

    def list(self) -> list[Artifact]:
        """Return all artifacts registered by this store.

        Returns:
            A copy of the registered artifact list.
        """
        return list(self._artifacts)
