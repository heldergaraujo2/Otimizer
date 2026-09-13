from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ParsedAddress:
    """Structured location evidence extracted from a free-form address."""

    original: str | None
    normalized: str | None
    number: str | None
    quadra: str | None
    lote: str | None


_QUADRA_RE = re.compile(
    r"\b(?:quadra|qd|q)\s*[:.=\-]?\s*([a-z0-9]+(?:[./-][a-z0-9]+)*)\b",
    re.IGNORECASE,
)
_LOTE_RE = re.compile(
    r"\b(?:lote|lt)\s*[:.=\-]?\s*([a-z0-9]+(?:[./-][a-z0-9]+)*)\b",
    re.IGNORECASE,
)
_NUMBER_AFTER_SEPARATOR_RE = re.compile(
    r"(?:^|[,;])\s*(?!q(?:d|uadra)?\b|l(?:t|ote)?\b)(\d+[a-z]?(?:[-/]\d+)?)\b",
    re.IGNORECASE,
)
_NUMBER_FALLBACK_RE = re.compile(
    r"\b(\d+[a-z]?(?:[-/]\d+)?)\b",
    re.IGNORECASE,
)
_LOCATION_MARKED_NUMBER_RE = re.compile(
    r"\b(?:q(?:d|uadra)?|l(?:t|ote)?)\s*[:.=\-]?\s*[a-z0-9]+(?:[./-][a-z0-9]+)*",
    re.IGNORECASE,
)


def normalize_address(value: str | None) -> str | None:
    """Normalize address text for matching without changing the original value."""
    if not value:
        return None
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _extract_field(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _extract_number(text: str) -> str | None:
    match = _NUMBER_AFTER_SEPARATOR_RE.search(text)
    if match:
        return match.group(1)

    upper = re.sub(r"[^A-Z0-9/]+", " ", text.upper())
    if re.search(r"\bS\s*/\s*N\b|\bSN\b|\bSEM\s+NUMERO\b", upper):
        return None

    # Do not mistake the numeric value belonging to Q/Qd/Quadra/Lt/Lote for
    # the house number when no comma-separated house-number segment exists.
    unmarked = _LOCATION_MARKED_NUMBER_RE.sub(" ", text)
    match = _NUMBER_FALLBACK_RE.search(unmarked)
    return match.group(1) if match else None


def parse_address(value: str | None) -> ParsedAddress:
    """Extract optional house number, Quadra and Lote from free-form text."""
    original = value.strip() if value and value.strip() else None
    if original is None:
        return ParsedAddress(None, None, None, None, None)

    return ParsedAddress(
        original=original,
        normalized=normalize_address(original),
        number=_extract_number(original),
        quadra=_extract_field(_QUADRA_RE, original),
        lote=_extract_field(_LOTE_RE, original),
    )
