"""Compatibility hooks for Goiânia cadastral geometry during the transition."""

from __future__ import annotations

import re

from . import goiania
from .location import LocationEvidence, ResolvedLocation


def _point_from_geometry(geometry: dict) -> tuple[float, float] | None:
    point = goiania._point_from_geometry_original(geometry)
    if point is not None:
        return point

    # Cadastro Imobiliário is polygonal. Use its representative point when the
    # ArcGIS response does not include a point geometry.
    return goiania._representative_point(geometry)


if not hasattr(goiania, "_point_from_geometry_original"):
    goiania._point_from_geometry_original = goiania._point_from_geometry
    goiania._point_from_geometry = _point_from_geometry


_original_resolve_uncached = goiania.GoianiaLocationProvider._resolve_uncached


def _street_search_terms(evidence: LocationEvidence) -> list[str]:
    """Extract useful street-name variants from an address-only evidence record."""
    raw = str(evidence.address or evidence.normalized_address or "").strip()
    if not raw:
        return []

    # Manual routes normally provide the street in ``address`` and the house
    # number separately. Still remove common address decorations so the query
    # remains useful for imported records too.
    raw = re.sub(r"\b(?:qd|q|quadra)\s*[\w-]+\b", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b(?:lt|lote)\s*[\w-]+\b", " ", raw, flags=re.IGNORECASE)
    if evidence.number:
        raw = re.sub(rf"\b{re.escape(str(evidence.number).strip())}\b", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s+", " ", raw).strip(" ,-")
    if not raw:
        return []

    terms = [raw]
    # Some municipal datasets keep the street type in a separate field. Query
    # both the user's full street text and the name without that prefix.
    without_type = re.sub(
        r"^(?:rua|r|avenida|av|alameda|al|travessa|tv|praça|pca|rodovia|rodo|estrada|est)\s+",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    if without_type and without_type.casefold() != raw.casefold():
        terms.append(without_type)
    return list(dict.fromkeys(terms))


def _street_point_from_geometry(geometry: dict) -> tuple[float, float] | None:
    """Return a point that lies on a returned municipal street polyline."""
    longest: tuple[float, tuple[float, float]] | None = None
    for path in (geometry or {}).get("paths") or []:
        for start, end in zip(path, path[1:]):
            try:
                sx, sy = float(start[0]), float(start[1])
                ex, ey = float(end[0]), float(end[1])
            except (TypeError, ValueError, IndexError):
                continue
            length_sq = (ex - sx) ** 2 + (ey - sy) ** 2
            if length_sq <= 0:
                continue
            midpoint = ((sx + ex) / 2.0, (sy + ey) / 2.0)
            if longest is None or length_sq > longest[0]:
                longest = (length_sq, midpoint)
    return longest[1] if longest is not None else None


def _resolve_on_municipal_street(
    self: goiania.GoianiaLocationProvider,
    evidence: LocationEvidence,
) -> ResolvedLocation | None:
    """Resolve an address-only stop to any valid point on its real street.

    Exact parcel resolution is intentionally not required here. The municipal
    ``Logradouro por Bairro`` layer is a polyline source, so a midpoint of one
    of its returned segments gives routing a real point on the requested road.
    """
    terms = _street_search_terms(evidence)
    if not terms:
        return None

    neighborhood = str(evidence.neighborhood or "").strip()
    features: list[dict] = []
    for term in terms:
        escaped = goiania._escape_where_value(term)
        where = f"(nm_log LIKE '%{escaped}%' OR nm LIKE '%{escaped}%')"
        if neighborhood:
            escaped_neighborhood = goiania._escape_where_value(neighborhood)
            with_neighborhood = f"{where} AND nm_bai LIKE '%{escaped_neighborhood}%'"
            features = self._query_layer_where(
                10,
                with_neighborhood,
                "id,tp_log,nm_log,nm,nm_bai",
            )
            if features:
                break
        features = self._query_layer_where(10, where, "id,tp_log,nm_log,nm,nm_bai")
        if features:
            break

    if not features:
        return None

    # Prefer the closest textual match, then the first real municipal feature.
    preferred = features[0]
    for feature in features:
        attrs = feature.get("attributes") or {}
        name = attrs.get("nm_log") or attrs.get("nm")
        if goiania._same_street_name(name, terms[0]):
            preferred = feature
            break

    route_point = _street_point_from_geometry(preferred.get("geometry") or {})
    if route_point is None:
        return None

    return ResolvedLocation(
        latitude=route_point[1],
        longitude=route_point[0],
        confidence=0.82 if neighborhood else 0.76,
        source="goiania-municipal-street",
        access_latitude=route_point[1],
        access_longitude=route_point[0],
    )


def _resolve_uncached_with_legacy_source(
    self: goiania.GoianiaLocationProvider,
    evidence: LocationEvidence,
) -> ResolvedLocation | None:
    resolved = _original_resolve_uncached(self, evidence)
    if resolved is not None:
        if (
            resolved.source == "goiania-cadastral-lot"
            and evidence.latitude is None
            and evidence.longitude is None
            and evidence.neighborhood
            and evidence.quadra
            and evidence.lote
        ):
            return ResolvedLocation(
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                confidence=resolved.confidence,
                source="goiania-cadastral-parcel",
                property_latitude=resolved.property_latitude,
                property_longitude=resolved.property_longitude,
                access_latitude=resolved.access_latitude,
                access_longitude=resolved.access_longitude,
                cadastral_id=resolved.cadastral_id,
            )
        return resolved

    # Last-resort manual/address path: a real municipal street is enough to
    # produce a routable point. This deliberately runs only after all existing
    # cadastral/GPS resolution paths have had their chance.
    return _resolve_on_municipal_street(self, evidence)


if not getattr(goiania.GoianiaLocationProvider._resolve_uncached, "_otimizer_legacy_source_patch", False):
    _resolve_uncached_with_legacy_source._otimizer_legacy_source_patch = True
    goiania.GoianiaLocationProvider._resolve_uncached = _resolve_uncached_with_legacy_source
