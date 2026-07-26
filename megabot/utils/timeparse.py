import re

DURATION_RE = re.compile(r"(\d+)(s|m|h|d)")
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> int | None:
    """Parses strings like '10m', '1h30m', '2d' into total seconds. Returns None if unparseable."""
    matches = DURATION_RE.findall(text.lower())
    if not matches:
        return None
    return sum(int(n) * UNIT_SECONDS[u] for n, u in matches)
