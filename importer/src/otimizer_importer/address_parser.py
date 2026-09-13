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
    r"\b(?:q|qd|quadra)\s*[:.=\-]?\s*([a-z0-9]+(?:[./-][a-z0-9]+)*)\b",
    re.IGNORECASE,
)
_LOTE_RE = re.compile(
    r"\b(?:lt|lote)\s*[:.=\-]?\s*([a-z0-9]+(?:[./-][a-z0-9]+)*)\b",
    re.IGNORECASE,
)
_NUMBER_AFTER_SEPARATOR_RE = re.compile(
    r"(?:^|[,;])\s*(\d+[a-z]?(?:[-/]\d+)?)\b",
    re.IGNORECASE,
)
_NUMBER_FALLBACK_RE = re.compile(
    r"\b(\d+[a-z]?(?:[-/]\d+)?)\b",
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
    # Prefer the number in an address segment after a comma/semicolon. This
    # avoids interpreting a street name such as "Rua PA 9" as the house number
    # when the actual number follows it ("Rua PA 9, 49, ...").
    match = _NUMBER_AFTER_SEPARATOR_RE.search(text)
    if match:
        return match.group(1)

    # "S/N", "SN" and "SEM NUMERO" explicitly mean that no house number is
    # available. They are not treated as numeric evidence.
    upper = re.sub(r"[^A-Z0-9/]+", " ", text.upper())
    if re.search(r"\bS\s*/\s*N\b|\bSN\b|\bSEM\s+NUMERO\b", upper):
        return None

    match = _NUMBER_FALLBACK_RE.search(text)
    return match.group(1) if match else None


def parse_address(value: str | None) -> ParsedAddress:
    """Extract optional house number, Quadra and Lote from free-form text.

    The parser is deliberately conservative: it only extracts a field when a
    recognizable Brazilian address marker is present and always preserves the
    original address for downstream geocoding/cadastral lookup.
    """
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
