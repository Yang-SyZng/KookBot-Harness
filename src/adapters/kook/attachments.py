import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.models import Attachment


class AttachmentError(ValueError):
    """Represent an error raised while validating or downloading an attachment."""

    pass


class AttachmentDownloader:
    def __init__(self, client: httpx.AsyncClient | None = None, max_bytes: int = 10 * 1024 * 1024):
        """Initialize the attachment downloader.

        Args:
            client: Optional HTTP client to reuse for download requests. If omitted,
                a temporary client is created for each download.
            max_bytes: Maximum allowed attachment size in bytes.
        """
        self._client = client
        self._max_bytes = max_bytes

    async def download_one(self, attachment: Attachment, workspace: Path) -> Path:
        """Download a single attachment into the task workspace.

        Args:
            attachment: Attachment metadata containing the source URL and filename.
            workspace: Task workspace where the attachment is stored.

        Returns:
            The resolved path of the downloaded attachment.

        Raises:
            AttachmentError: If the URL scheme or destination path is invalid, or
                if the attachment exceeds the configured size limit.
            httpx.HTTPStatusError: If the server returns an unsuccessful HTTP
                response.
        """
        parsed = urlparse(attachment.url)
        if parsed.scheme not in {"http", "https"}:
            raise AttachmentError("The attachment URL must use HTTP or HTTPS.")

        name = Path(attachment.name or Path(parsed.path).name or "attachment").name
        input_dir = workspace.resolve() / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        destination = (input_dir / name).resolve()
        if destination.parent != input_dir:
            raise AttachmentError("The attachment path is outside the input directory.")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(follow_redirects=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".download-", dir=input_dir)
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as handle:
                async with client.stream("GET", attachment.url) as response:
                    response.raise_for_status()
                    length = response.headers.get("content-length")
                    if length and int(length) > self._max_bytes:
                        raise AttachmentError("The attachment exceeds the size limit.")
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self._max_bytes:
                            raise AttachmentError("The attachment exceeds the size limit.")
                        handle.write(chunk)
            Path(temporary_name).replace(destination)
            return destination
        finally:
            Path(temporary_name).unlink(missing_ok=True)
            if owns_client:
                await client.aclose()
