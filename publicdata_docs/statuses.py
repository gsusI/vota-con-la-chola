from __future__ import annotations


class HTTPStatusError(RuntimeError):
    """HTTP-like error carrying a status code for fetch ledgers."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = int(code)


def normalize_archive_fallback_http_statuses(
    values: tuple[int, ...] | list[int] | None,
    *,
    default: tuple[int, ...] = (404,),
) -> tuple[int, ...]:
    if values is None:
        return tuple(int(v) for v in default)
    parsed = _normalize_status_values(values, allow_zero=False)
    if parsed:
        return parsed
    return tuple(int(v) for v in default)


def normalize_http_status_filter(values: tuple[int, ...] | list[int] | None) -> tuple[int, ...]:
    if not values:
        return tuple()
    return _normalize_status_values(values, allow_zero=True)


def _normalize_status_values(values: tuple[int, ...] | list[int], *, allow_zero: bool) -> tuple[int, ...]:
    parsed: list[int] = []
    seen: set[int] = set()
    for raw in values:
        try:
            code = int(raw)
        except Exception:  # noqa: BLE001
            continue
        if code in seen:
            continue
        if code == 0 and allow_zero:
            seen.add(code)
            parsed.append(code)
            continue
        if code < 100 or code > 599:
            continue
        seen.add(code)
        parsed.append(code)
    return tuple(parsed)
