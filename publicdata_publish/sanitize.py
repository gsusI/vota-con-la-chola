from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEY_TOKENS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "key",
    "auth",
    "authorization",
    "cookie",
    "signature",
    "sig",
)
HF_TOKEN_RE = re.compile(r"\bhf_[A-Za-z0-9]{16,}\b")
BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}")
SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|passwd|secret|cookie|access_token|refresh_token|client_secret)\b\s*[:=]\s*([^\s,;]+)"
)
AUTH_KV_RE = re.compile(r"(?i)\bauthorization\b\s*[:=]\s*(?!bearer\b)([^\s,;]+)")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LOCAL_USERS_PREFIX = "/" + "Users" + "/"
LOCAL_HOME_PREFIX = "/" + "home" + "/"
LOCAL_USER_SEGMENT_RE = re.compile(re.escape(LOCAL_USERS_PREFIX) + r"[^/\s]+")
LOCAL_HOME_SEGMENT_RE = re.compile(re.escape(LOCAL_HOME_PREFIX) + r"[^/\s]+")


def is_sensitive_query_key(name: str) -> bool:
    lowered = name.strip().lower().replace("-", "_")
    return any(token in lowered for token in SENSITIVE_QUERY_KEY_TOKENS)


def is_sensitive_query_value(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return False
    lowered = raw.lower()
    if lowered.startswith("bearer "):
        return True
    if HF_TOKEN_RE.search(raw):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]{32,}", raw))


def redact_sensitive_text(value: str) -> str:
    redacted = BEARER_RE.sub(r"\1 REDACTED", value)
    redacted = HF_TOKEN_RE.sub("hf_REDACTED", redacted)
    redacted = AUTH_KV_RE.sub("authorization=REDACTED", redacted)

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}=REDACTED"

    redacted = SENSITIVE_KV_RE.sub(repl, redacted)
    redacted = EMAIL_RE.sub("<redacted-email>", redacted)
    redacted = LOCAL_USER_SEGMENT_RE.sub(LOCAL_USERS_PREFIX + "<redacted-user>", redacted)
    redacted = LOCAL_HOME_SEGMENT_RE.sub(LOCAL_HOME_PREFIX + "<redacted-user>", redacted)
    return redacted


def sanitize_url_for_public(raw_url: str) -> str:
    text = raw_url.strip()
    if not text:
        return text
    if text.lower().startswith("file://"):
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return redact_sensitive_text(text)

    query_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if is_sensitive_query_key(key) or is_sensitive_query_value(value):
            query_pairs.append((key, "REDACTED"))
        else:
            query_pairs.append((key, redact_sensitive_text(value)))
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    query = urlencode(query_pairs, doseq=True)
    safe_path = HF_TOKEN_RE.sub("hf_REDACTED", parsed.path)
    return urlunsplit((parsed.scheme, netloc, safe_path, query, ""))
