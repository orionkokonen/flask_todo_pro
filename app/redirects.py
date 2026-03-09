from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import request


def is_safe_redirect_target(target: str) -> bool:
    """Allow only same-origin http(s) redirect targets."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def safe_redirect_target(target: str | None, fallback: str) -> str:
    """Return the target when it is safe, otherwise the fallback."""
    if target and is_safe_redirect_target(target):
        return target
    return fallback


def safe_referrer_or(fallback: str) -> str:
    """Return request.referrer only when it points back to this app."""
    return safe_redirect_target(request.referrer, fallback)
