import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class MessageDeduplicator:
    """File-based message deduplicator for idempotent event processing.

    Atomically creates a state file for each message ID so that only one worker
    can claim and process a message. This prevents duplicate agent runs and bot
    replies caused by event retries, reconnections, or concurrent consumers.

    State files are named using the SHA-256 digest of the message ID and record
    one of three states: processing, completed, or failed.

    Note:
        A message cannot be claimed again once its state file exists. Messages
        left in the processing state after a crash, as well as failed messages,
        are therefore not retried automatically. Add lease expiration and retry
        handling if recovery is required.
    """

    def __init__(self, root: Path) -> None:
        """Initialize the deduplicator and create its state directory.

        Args:
            root: Directory in which message state files are stored.
        """
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, message_id: str) -> Path:
        """Build a safe, fixed-length state-file path for a message.

        Args:
            message_id: Unique KOOK message identifier.

        Returns:
            The path derived from the SHA-256 digest of the message ID.
        """
        digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()
        return self._root / f"{digest}.json"

    def claim(self, message_id: str) -> bool:
        """Attempt to claim exclusive processing rights for a message.

        The state file is created atomically with O_CREAT and O_EXCL, ensuring
        that only one caller succeeds even when multiple workers attempt to
        claim the same message concurrently.

        Args:
            message_id: Unique KOOK message identifier.

        Returns:
            ``True`` if the message was claimed successfully; ``False`` if it was
            already claimed or processed.
        """
        path = self._path(message_id)
        payload = json.dumps({
            "message_id": message_id,
            "status": "processing",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        return True

    def mark(self, message_id: str, status: str) -> None:
        """Record the final processing status of a claimed message.

        The new state is written to a temporary file and then atomically
        replaces the existing state file to avoid leaving partially written
        JSON data.

        Args:
            message_id: Unique KOOK message identifier.
            status: Final status, either "completed" or "failed".

        Raises:
            ValueError: If status is not "completed" or "failed".
        """
        if status not in {"completed", "failed"}:
            raise ValueError(f"unsupported dedupe status: {status}")
        path = self._path(message_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "message_id": message_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
        temporary.replace(path)
