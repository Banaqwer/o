"""Minimal HTTP GET with retries, Retry-After handling and an on-disk cache."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional

USER_AGENT = "atm-engine/0.1 (+https://github.com/Banaqwer/o)"


@dataclass(frozen=True)
class Response:
    status: int
    headers: Dict[str, str]  # lower-cased keys
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding, errors="replace")

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def retry_after(self, default: float) -> float:
        v = self.headers.get("retry-after")
        try:
            return float(v) if v is not None else default
        except ValueError:
            return default


Transport = Callable[[str, Mapping[str, str], float], Response]


def urllib_transport(url: str, headers: Mapping[str, str], timeout: float) -> Response:
    """Default transport. urllib honours HTTPS_PROXY and the system CA bundle."""

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return Response(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, body)


class HttpClient:
    """GET with bounded retries on transport errors and 5xx, honouring Retry-After."""

    def __init__(
        self,
        transport: Transport = urllib_transport,
        timeout: float = 60.0,
        retries: int = 3,
        backoff: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        cache_dir: Optional[str | Path] = None,
        cache_ttl: float = 24 * 3600.0,
    ):
        self.transport = transport
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_ttl = cache_ttl
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def build_url(base: str, params: Optional[Mapping[str, object]] = None) -> str:
        if not params:
            return base
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, safe=":,/ ")
        return f"{base}?{q}"

    def _cache_path(self, url: str) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".bin")

    def get(self, url: str, headers: Optional[Mapping[str, str]] = None, use_cache: bool = False) -> Response:
        path = self._cache_path(url) if use_cache else None
        if path and path.exists() and (time.time() - path.stat().st_mtime) < self.cache_ttl:
            return Response(200, {"x-cache": "hit"}, path.read_bytes())
        attempt = 0
        while True:
            try:
                resp = self.transport(url, headers or {}, self.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                attempt += 1
                if attempt > self.retries:
                    raise ConnectionError(f"GET {url} failed after {self.retries} retries: {e}") from e
                self.sleep(self.backoff**attempt)
                continue
            if resp.status in (502, 503, 504) and attempt < self.retries:
                attempt += 1
                self.sleep(resp.retry_after(self.backoff**attempt))
                continue
            if resp.ok and path:
                path.write_bytes(resp.body)
            return resp
