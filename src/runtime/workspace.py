import hashlib
from pathlib import Path


def task_workspace(root: Path, user_id: str, request_id: str) -> Path:
    """Create and return an isolated workspace for a user request.

    Args:
        root: Root directory containing all task workspaces.
        user_id: Identifier of the user that submitted the request.
        request_id: Unique identifier of the request.

    Returns:
        The resolved path of the task-specific workspace.
    """
    user_key = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:20]
    request_key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:24]
    workspace = root.resolve() / user_key / request_key
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace
