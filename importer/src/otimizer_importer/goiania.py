"""Goiânia cadastral location provider.

The provider uses the municipality's public ArcGIS FeatureServer as an
optional source of cadastral evidence. It is intentionally isolated from the
core location abstractions so other cities can provide their own adapters.
"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .location import LocationDataProvider, LocationEvidence, ResolvedLocation

DEFAULT_FEATURE_BASE_URL = (
    "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/"
    "MapaServer/Feature_Base/FeatureServer"
)
LOT_LAYER_ID = 0


class GoianiaLocationProvider(LocationDataProvider):
    """Resolve an XLSX GPS point against Goiânia's public cadastral layers.

    The XLSX GPS coordinate is the search anchor. The returned location is a
    cadastral property evidence point, not a claimed vehicle stopping point.
    A later access-point resolver can use the property geometry and road data.
    """

    def __init__(self, *, base_url: str = DEFAULT_FEATURE_BASE_URL, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def resolve(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        if (evidence.city or "").strip().casefold() not in {"goiania", "goiânia"}:
            return None

        features = self._query_lots(evidence)
        if not features:
            return None

        best = min(features, key=lambda feature: _distance_sq_to_geometry(evidence, feature.get("geometry") or {}))
        geometry = best.get("geometry") or {}
        point = _representative_point(geometry)
        if point is None:
            return None

        attributes = best.get("attributes") or {}
        cadastral_id = attributes.get("id")
        return ResolvedLocation(
            latitude=point[1],
            longitude=point[0],
            confidence=0.80,
            source="goiania-cadastral-lot",
            property_latitude=point[1],
            property_longitude=point[0],
            cadastral_id=str(cadastral_id) if cadastral_id is not None else None,
        )

    def _query_lots(self, evidence: LocationEvidence) -> list[dict]:
        # Small envelope around the GPS pin: useful when the delivery pin is
        # on the street beside the cadastral polygon. Exact address/lot
        # matching and vehicle access-point selection remain separate stages.
        delta = 0.0005
        params = {
            "where": "1=1",
            "geometry": f"{evidence.longitude - delta},{evidence.latitude - delta},{evidence.longitude + delta},{evidence.latitude + delta}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "id,id_qdr,nm_lot,nm_imovel,id_seg",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": "10",
            "f": "json",
        }
        url = f"{self.base_url}/{LOT_LAYER_ID}/query?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Otimizer/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        return payload.get("features") or []


def _representative_point(geometry: dict) -> tuple[float, float] | None:
    """Return a polygon centroid for the first ArcGIS ring."""
    rings = geometry.get("rings")
    if not rings or not rings[0] or len(rings[0]) < 3:
        return None
    points = rings[0]
    area_twice = 0.0
    cx = 0.0
    cy = 0.0
    for current, nxt in zip(points, points[1:] + points[:1]):
        cross = current[0] * nxt[1] - nxt[0] * current[1]
        area_twice += cross
        cx += (current[0] + nxt[0]) * cross
        cy += (current[1] + nxt[1]) * cross
    if abs(area_twice) < 1e-12:
        return points[0][0], points[0][1]
    return cx / (3 * area_twice), cy / (3 * area_twice)


def _distance_sq_to_geometry(evidence: LocationEvidence, geometry: dict) -> float:
    point = _representative_point(geometry)
    if point is None:
        return float("inf")
    return (point[0] - evidence.longitude) ** 2 + (point[1] - evidence.latitude) ** 2
