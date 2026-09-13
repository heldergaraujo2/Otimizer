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
PROPERTY_NUMBER_LAYER_ID = 5


class GoianiaLocationProvider(LocationDataProvider):
    """Resolve an XLSX GPS point against Goiânia's public cadastral layers.

    This first adapter deliberately treats the XLSX GPS coordinate as the
    search anchor. It does not pretend that cadastral polygons are the
    vehicle's stopping point: the returned location is a property/cadastral
    evidence point and can later feed an access-point resolver.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_FEATURE_BASE_URL,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def resolve(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        if (evidence.city or "").strip().casefold() not in {"goiania", "goiânia"}:
            return None

        lot = self._query_layer(
            LOT_LAYER_ID,
            evidence,
            out_fields="id,id_qdr,nm_lot,nm_imovel,id_seg",
        )
        if not lot:
            return None

        feature = lot[0]
        geometry = feature.get("geometry") or {}
        point = _representative_point(geometry)
        if point is None:
            return None

        attributes = feature.get("attributes") or {}
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

    def _query_layer(
        self,
        layer_id: int,
        evidence: LocationEvidence,
        *,
        out_fields: str,
    ) -> list[dict]:
        # A small envelope makes the first adapter useful even when the GPS
        # pin is on the road immediately beside a cadastral polygon. Exact
        # property/access matching remains a later resolver stage.
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
            "resultRecordCount": "5",
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


def _representative_point(geometry: dict) -> tuple[float, float] | None:
    """Return a safe representative point from ArcGIS polygon geometry."""
    rings = geometry.get("rings")
    if not rings or not rings[0]:
        return None
    points = rings[0]
    longitude = sum(point[0] for point in points) / len(points)
    latitude = sum(point[1] for point in points) / len(points)
    return longitude, latitude
