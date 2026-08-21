import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import getproxies

import httpx

log = logging.getLogger(__name__)


MODEL_PRICING_URLS = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/model_prices_and_context_window_backup.json",
)

DEFAULT_MODEL_PRICING_PATH = Path(__file__).resolve().parent / "model_price.json"
PROXY_CONNECT_TIMEOUT = 1.0
ETAG_METADATA_SUFFIX = ".etag.json"


class ModelPricingDownloadError(RuntimeError):
    """Raised when model pricing data cannot be downloaded from any source."""

def INFO(verbose, message: str) -> None:
    """Log an informational message when verbose output is requested."""
    if verbose:
        log.info("%s", message)

def _configured_proxy() -> str | None:
    """Return the environment proxy most suitable for HTTPS downloads."""
    proxies = getproxies()
    return proxies.get("https") or proxies.get("all") or proxies.get("http")


async def _proxy_is_reachable(proxy_url: str, timeout: float) -> bool:
    """Check whether the configured proxy's TCP endpoint accepts connections."""
    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    host = parsed.hostname
    if not host:
        return False

    default_ports = {
        "http": 80,
        "https": 443,
        "socks4": 1080,
        "socks5": 1080,
        "socks5h": 1080,
    }
    try:
        port = parsed.port or default_ports.get(parsed.scheme.lower())
    except ValueError:
        return False
    if port is None:
        return False

    writer = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        return True
    except (OSError, asyncio.TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()


async def _create_http_client(
    timeout: float, reporter: Callable[[str], None] | None = None
) -> httpx.AsyncClient:
    """Use a working environment proxy, otherwise create a direct client."""
    proxy_url = _configured_proxy()
    use_proxy = proxy_url is not None and await _proxy_is_reachable(
        proxy_url, min(timeout, PROXY_CONNECT_TIMEOUT)
    )
    if reporter:
        reporter("An available proxy was detected and a connection was established using the proxy." if use_proxy else "No available proxy was detected. Using direct connection instead.")
    else:
        log.info("An available proxy was detected and a connection was established using the proxy." if use_proxy else "No available proxy was detected. Using direct connection instead.")
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        proxy=proxy_url if use_proxy else None,
        trust_env=False,
    )


def _etag_metadata_path(target: Path) -> Path:
    return target.with_name(f"{target.name}{ETAG_METADATA_SUFFIX}")


def _load_etag_metadata(target: Path) -> tuple[str, str] | None:
    """Return the source URL and ETag saved for an existing pricing file."""
    if not target.is_file():
        return None

    try:
        metadata = json.loads(_etag_metadata_path(target).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    url = metadata.get("url") if isinstance(metadata, dict) else None
    etag = metadata.get("etag") if isinstance(metadata, dict) else None
    if not isinstance(url, str) or not isinstance(etag, str):
        return None
    return url, etag


def _atomic_write_json(target: Path, data: object) -> None:
    """Atomically serialize JSON to target without leaving partial files behind."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        Path(temporary_name).replace(target)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def _save_etag_metadata(target: Path, url: str, etag: str | None) -> None:
    """Persist the validator for the just-downloaded pricing file."""
    metadata_path = _etag_metadata_path(target)
    if etag:
        _atomic_write_json(metadata_path, {"url": url, "etag": etag})
    else:
        metadata_path.unlink(missing_ok=True)


async def download_model_pricing(
    destination: Path | str = DEFAULT_MODEL_PRICING_PATH,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
    verbose: bool = False,
) -> Path:
    """Refresh LiteLLM model pricing data, falling back between known sources.

    A reachable proxy from the environment is used automatically. If no proxy is
    configured, or its TCP endpoint cannot be reached, the download goes direct.
    An explicitly supplied client is used unchanged.

    The ETag returned by a source is saved next to the pricing file. A later
    refresh sends it as ``If-None-Match``; a ``304 Not Modified`` response keeps
    the existing file without downloading it again.

    Set ``verbose=True`` to log refresh progress details.
    """
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    owns_client = client is None

    def report(message: str) -> None:
        """Emit download progress through the logging framework."""
        log.info("%s", message)

    http_client = client or await _create_http_client(timeout, report)
    if client is not None:
        report("使用调用方提供的 HTTP 客户端。")
    failures: list[str] = []
    etag_metadata = _load_etag_metadata(target)
    if etag_metadata and etag_metadata[0] not in MODEL_PRICING_URLS:
        etag_metadata = None
    cached_url = etag_metadata[0] if etag_metadata else None
    urls = tuple(dict.fromkeys((cached_url, *MODEL_PRICING_URLS))) if cached_url else MODEL_PRICING_URLS
    if etag_metadata:
        report("检测到本地 ETag 缓存，正在向云端检查更新。")
    else:
        report("本地没有可用 ETag 缓存，正在下载完整价格表。")

    try:
        for url in urls:
            try:
                headers = (
                    {"If-None-Match": etag_metadata[1]}
                    if etag_metadata and url == etag_metadata[0]
                    else None
                )
                response = await http_client.get(url, headers=headers)
                if response.status_code == httpx.codes.NOT_MODIFIED:
                    if etag_metadata and url == etag_metadata[0]:
                        report("云端价格表未更新，继续使用本地文件。")
                        return target
                    raise httpx.HTTPStatusError(
                        "Unexpected 304 response without a local ETag cache",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("the response root must be a JSON object")

                _atomic_write_json(target, data)
                _save_etag_metadata(target, url, response.headers.get("etag"))
                report(f"已下载并更新价格表：{target}")

                return target
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                reason = str(exc) or type(exc).__name__
                failures.append(f"{url}: {reason}")
                report(f"下载源失败，尝试下一个备用源：{reason}")
    finally:
        if owns_client:
            await http_client.aclose()

    details = "; ".join(failures)
    report("所有下载源均不可用。")
    raise ModelPricingDownloadError(f"Unable to download model pricing data: {details}")


def load_model_pricing(
    data_path: Path | str = DEFAULT_MODEL_PRICING_PATH,
) -> dict:
    """Load the model pricing table from disk as a dictionary.

    Args:
        data_path: JSON file produced by :func:`download_model_pricing`.

    Returns:
        The pricing table where each key maps to a model's pricing config.

    Raises:
        OSError: If the file cannot be read.
        json.JSONDecodeError: If the file does not contain valid JSON.
    """
    return json.loads(Path(data_path).read_text(encoding="utf-8"))


def find_model_price_keys(
    node: object, target_keyword: str, current_path: str = ""
) -> list[tuple[str, str, object]]:
    """Recursively collect keys whose name contains ``target_keyword``.

    Args:
        node: The JSON-derived object to search (dict, list, or scalar).
        target_keyword: Substring to match against every key name.
        current_path: Dot/bracket path built up during recursion.

    Returns:
        A list of ``(key, full_path, value)`` tuples for every matching key.
    """
    results: list[tuple[str, str, object]] = []

    if isinstance(node, dict):
        for k, v in node.items():
            next_path = f"{current_path}['{k}']" if current_path else f"['{k}']"
            if target_keyword in k:
                results.append((k, next_path, v))
            results.extend(find_model_price_keys(v, target_keyword, next_path))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            next_path = f"{current_path}[{index}]"
            results.extend(find_model_price_keys(item, target_keyword, next_path))

    return results


async def query_model_pricing(
    model_id: str | None = None,
    data_path: Path | str = DEFAULT_MODEL_PRICING_PATH,
    *,
    verbose: bool = False,
) -> dict | None:
    """Refresh the pricing table, then return the config whose key matches.

    The pricing data is refreshed via :func:`download_model_pricing` before any
    lookup happens so the most up-to-date prices are used. If the refresh fails
    (e.g. network is unavailable) the existing local pricing file is used as a
    fallback and a warning is logged.

    When ``model_id`` is ``None``, the value of ``AppSettings.llm_model_id`` is
    used as the lookup keyword. Matching is a case-sensitive substring match on
    the pricing table keys (e.g. ``deepseek-ai/DeepSeek-V4-Flash`` matches a key
    such as ``azure_ai/deepseek-v4-flash`` with the exact substring present).

    Args:
        model_id: The model identifier to look up. Defaults to
            ``AppSettings.llm_model_id``.
        data_path: JSON file containing the pricing table. Passed to
            :func:`download_model_pricing` so the file is refreshed in place.
        verbose: When ``True``, log details of every match found.

    Returns:
        The pricing config (dict) for the first matching key, or ``None`` when
        no key matches.
    """
    if model_id is None:
        from src import AppSettings

        model_id = AppSettings().llm_model_id

    try:
        await download_model_pricing(destination=data_path, verbose=True)
    except ModelPricingDownloadError as exc:
        log.warning("failed to refresh model pricing, falling back to local data: %s", exc)
    except OSError as exc:
        log.warning("could not refresh model pricing data, falling back to local data: %s", exc)

    data = await asyncio.to_thread(load_model_pricing, data_path)
    matches = find_model_price_keys(data, model_id)

    if verbose:
        for key, full_path, value in matches:
            log.info(
                "pricing match: key=%r path=%s value=%s",
                key,
                full_path,
                json.dumps(value, ensure_ascii=False),
            )

    if not matches:
        return None
    # The first match is the shallowest/most specific key found during the
    # recursive traversal.
    return matches[0][2]


__all__ = [
    "DEFAULT_MODEL_PRICING_PATH",
    "ETAG_METADATA_SUFFIX",
    "MODEL_PRICING_URLS",
    "ModelPricingDownloadError",
    "download_model_pricing",
    "load_model_pricing",
    "find_model_price_keys",
    "query_model_pricing",
]
