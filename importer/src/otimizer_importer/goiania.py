"""Goiânia cadastral location provider.

The provider uses the municipality's public ArcGIS FeatureServer as an
optional source of cadastral evidence. It is intentionally isolated from the
core location abstractions so other cities can provide their own adapters.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .location import LocationDataProvider, LocationEvidence, ResolvedLocation

DEFAULT_FEATURE_BASE_URL = (
    "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/"
    "MapaServer/Feature_Base/FeatureServer"
)
LOT_LAYER_ID = 0
OFFICIAL_NUMBER_LAYER_ID = 5


class GoianiaLocationProvider(LocationDataProvider):
    """Resolve an XLSX GPS point against Goiânia's public cadastral layers.

    The XLSX GPS coordinate is the search anchor. When the spreadsheet has a
    house number, an exact municipal official-number match is preferred because
    that point is normally a better frontage/property anchor than a lot
    centroid. Without a number match, the cadastral lot remains the fallback.
    Neither result is claimed to be the final vehicle stopping point; that is
    a separate road-access stage.
    """

    def __init__(self, *, base_url: str = DEFAULT_FEATURE_BASE_URL, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def resolve(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        if (evidence.city or "").strip().casefold() not in {"goiania", "goiânia"}:
            return None

        if evidence.number:
            official_numbers = self._query_official_numbers(evidence)
            best_number = _best_matching_official_number(evidence, official_numbers)
            if best_number is not None:
                geometry = best_number.get("geometry") or {}
                point = _point_from_geometry(geometry)
                if point is not None:
                    attributes = best_number.get("attributes") or {}
                    cadastral_id = attributes.get("id")
                    return ResolvedLocation(
                        latitude=point[1],
                        longitude=point[0],
                        confidence=0.92,
                        source="goiania-official-property-number",
                        property_latitude=point[1],
                        property_longitude=point[0],
                        cadastral_id=str(cadastral_id) if cadastral_id is not None else None,
                    )

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
        return self._query_layer(evidence, LOT_LAYER_ID, "id,id_qdr,nm_lot,nm_imovel,id_seg")

    def _query_official_numbers(self, evidence: LocationEvidence) -> list[dict]:
        return self._query_layer(evidence, OFFICIAL_NUMBER_LAYER_ID, "id,nm_npo,cd_log,cd_rua,cd_bai,ci")

    def _query_layer(self, evidence: LocationEvidence, layer_id: int, out_fields: str) -> list[dict]:
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
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": "25",
            "f": "json",
        }
        url = f"{self.base_url}/{layer_id}/query?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Otimizer/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        return payload.get("features") or []


def _point_from_geometry(geometry: dict) -> tuple[float, float] | None:
    """Return an ArcGIS point geometry when the layer exposes one."""
    x = geometry.get("x")
    y = geometry.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def _normalize_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text or None


def _best_matching_official_number(evidence: LocationEvidence, features: list[dict]) -> dict | None:
    target = _normalize_number(evidence.number)
    if target is None:
        return None
    matches: list[dict] = []
    for feature in features:
        attributes = feature.get("attributes") or {}
        official_number = _normalize_number(attributes.get("nm_npo"))
        if official_number == target:
            matches.append(feature)
    if not matches:
        return None
    return min(matches, key=lambda feature: _distance_sq_to_geometry(evidence, feature.get("geometry") or {}))


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
    point = _point_from_geometry(geometry) or _representative_point(geometry)
    if point is None:
        return float("inf")
    return (point[0] - evidence.longitude) ** 2 + (point[1] - evidence.latitude) ** 2
