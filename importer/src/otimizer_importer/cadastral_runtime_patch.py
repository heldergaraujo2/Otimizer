"""Compatibility hooks for Goiânia cadastral geometry during the transition."""

from __future__ import annotations

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


def _resolve_uncached_with_legacy_source(
    self: goiania.GoianiaLocationProvider,
    evidence: LocationEvidence,
) -> ResolvedLocation | None:
    resolved = _original_resolve_uncached(self, evidence)
    if (
        resolved is not None
        and resolved.source == "goiania-cadastral-lot"
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


if not getattr(goiania.GoianiaLocationProvider._resolve_uncached, "_otimizer_legacy_source_patch", False):
    _resolve_uncached_with_legacy_source._otimizer_legacy_source_patch = True
    goiania.GoianiaLocationProvider._resolve_uncached = _resolve_uncached_with_legacy_source
