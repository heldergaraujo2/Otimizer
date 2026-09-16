"""Goiânia cadastral location provider."""

from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .location import LocationDataProvider, LocationEvidence, ResolvedLocation

DEFAULT_FEATURE_BASE_URL = (
    "https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/"
    "MapaServer/Feature_Base/FeatureServer"
)
LOT_LAYER_ID = 0
BLOCK_LAYER_ID = 1
NEIGHBORHOOD_LAYER_ID = 2
CADASTRAL_LAYER_ID = 3
OFFICIAL_NUMBER_LAYER_ID = 5
STREET_SEGMENT_LAYER_ID = 7


class _ApproximateResolvedLocation(ResolvedLocation):
    @property
    def is_approximate(self) -> bool:
        return True


class GoianiaLocationProvider(LocationDataProvider):
    """Resolve delivery evidence using Goiânia cadastral data."""

    def __init__(self, *, base_url: str = DEFAULT_FEATURE_BASE_URL, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._resolution_cache: dict[tuple[object, ...], ResolvedLocation | None] = {}

    def resolve(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        if (evidence.city or "").strip().casefold() not in {"goiania", "goiânia"}:
            return None

        cache_key = _resolution_cache_key(evidence)
        if cache_key in self._resolution_cache:
            return self._resolution_cache[cache_key]

        resolved = self._resolve_uncached(evidence)
        self._resolution_cache[cache_key] = resolved
        return resolved

    def _resolve_uncached(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        # The municipal Cadastro Imobiliário is the strongest cross-check when
        # quadra+lote are present. It contains address number, street, block,
        # lot and neighborhood in the same record, avoiding an early decision
        # based only on the first matching neighborhood/block polygon.
        if evidence.quadra and evidence.lote:
            cadastral_features = self._query_cadastral_by_parcel(evidence)
            best_cadastral = _best_matching_cadastral_record(evidence, cadastral_features)
            if best_cadastral is not None:
                property_point = _point_from_geometry(best_cadastral.get("geometry") or {})
                if property_point is None:
                    property_point = _cadastral_coordinate_point(best_cadastral.get("attributes") or {})
                if property_point is not None:
                    attributes = best_cadastral.get("attributes") or {}
                    cadastral_id = attributes.get("id") or attributes.get("ci") or attributes.get("nrinscr")
                    exact_number = _same_normalized_value(attributes.get("nrimovel"), evidence.number)
                    exact_street = _same_street_name(attributes.get("nmlogradou"), evidence.normalized_address)
                    access_point = self._nearest_street_access(property_point)
                    if access_point is not None:
                        confidence = 0.97 if exact_number and exact_street else 0.95 if exact_number else 0.92
                        source = "goiania-cadastral-crosscheck-road-access"
                        return _resolved_with_access(
                            property_point,
                            access_point,
                            confidence=confidence,
                            source=source,
                            cadastral_id=cadastral_id,
                        )
                    confidence = 0.93 if exact_number and exact_street else 0.90 if exact_number else 0.86
                    return _resolved_with_access(
                        property_point,
                        None,
                        confidence=confidence,
                        source="goiania-cadastral-crosscheck",
                        cadastral_id=cadastral_id,
                    )

        if evidence.latitude is None or evidence.longitude is None:
            features = self._query_lot_by_parcel(evidence)
            if not features:
                return None

            best = features[0]
            property_point = _representative_point(best.get("geometry") or {})
            if property_point is None:
                return None

            attributes = best.get("attributes") or {}
            cadastral_id = attributes.get("id")
            access_point = self._nearest_street_access(property_point)
            if access_point is not None:
                return _resolved_with_access(
                    property_point,
                    access_point,
                    confidence=0.88,
                    source="goiania-cadastral-lot-road-access",
                    cadastral_id=cadastral_id,
                )
            return _resolved_with_access(
                property_point,
                None,
                confidence=0.80,
                source="goiania-cadastral-lot",
                cadastral_id=cadastral_id,
            )

        if evidence.number:
            official_numbers = self._query_official_numbers(evidence)
            best_number = _best_matching_official_number(evidence, official_numbers)
            if best_number is not None:
                property_point = _point_from_geometry(best_number.get("geometry") or {})
                if property_point is not None:
                    attributes = best_number.get("attributes") or {}
                    cadastral_id = attributes.get("id")
                    access_point = self._nearest_street_access(property_point)
                    if access_point is not None:
                        return _resolved_with_access(
                            property_point,
                            access_point,
                            confidence=0.96,
                            source="goiania-official-property-number-road-access",
                            cadastral_id=cadastral_id,
                        )
                    return _resolved_with_access(
                        property_point,
                        None,
                        confidence=0.92,
                        source="goiania-official-property-number",
                        cadastral_id=cadastral_id,
                    )

        features = self._query_lots(evidence)
        if not features:
            return self._street_fallback(evidence)
        best = min(features, key=lambda feature: _distance_sq_to_geometry(evidence, feature.get("geometry") or {}))
        property_point = _representative_point(best.get("geometry") or {})
        if property_point is None:
            return self._street_fallback(evidence)

        attributes = best.get("attributes") or {}
        cadastral_id = attributes.get("id")
        access_point = self._nearest_street_access(property_point)
        if access_point is not None:
            return _resolved_with_access(
                property_point,
                access_point,
                confidence=0.88,
                source="goiania-cadastral-lot-road-access",
                cadastral_id=cadastral_id,
            )
        return _resolved_with_access(
            property_point,
            None,
            confidence=0.80,
            source="goiania-cadastral-lot",
            cadastral_id=cadastral_id,
        )

    def _street_fallback(self, evidence: LocationEvidence) -> ResolvedLocation | None:
        """Use the known street segment as an explicitly approximate route point."""
        if evidence.latitude is None or evidence.longitude is None:
            return None
        segments = self._query_street_segments(evidence.latitude, evidence.longitude)
        if not segments:
            return None

        property_point = (evidence.longitude, evidence.latitude)
        best: tuple[float, tuple[float, float]] | None = None
        for feature in segments:
            for path in (feature.get("geometry") or {}).get("paths") or []:
                for start, end in zip(path, path[1:]):
                    candidate = _nearest_point_on_segment(property_point, start, end)
                    distance = (candidate[0] - property_point[0]) ** 2 + (candidate[1] - property_point[1]) ** 2
                    if best is None or distance < best[0]:
                        best = (distance, candidate)
        if best is None:
            return None

        route_point = best[1]
        return _ApproximateResolvedLocation(
            latitude=route_point[1],
            longitude=route_point[0],
            confidence=0.55,
            source="goiania-street-fallback",
            property_latitude=evidence.latitude,
            property_longitude=evidence.longitude,
            access_latitude=route_point[1],
            access_longitude=route_point[0],
        )

    def _query_lots(self, evidence: LocationEvidence) -> list[dict]:
        return self._query_layer_at_point(
            evidence.latitude,
            evidence.longitude,
            LOT_LAYER_ID,
            "id,id_qdr,nm_lot,nm_imovel,id_seg",
        )

    def _query_cadastral_by_parcel(self, evidence: LocationEvidence) -> list[dict]:
        """Query the municipal property register directly using parcel evidence."""
        if not evidence.quadra or not evidence.lote:
            return []

        where = (
            f"nrquadra = '{_escape_where_value(evidence.quadra)}' "
            f"AND nrlote = '{_escape_where_value(evidence.lote)}'"
        )
        if evidence.neighborhood:
            where += f" AND nmbairro LIKE '%{_escape_where_value(evidence.neighborhood)}%'"

        return self._query_layer_where(
            CADASTRAL_LAYER_ID,
            where,
            "id,id_qdr,nrinscr,cdlogradou,nmlogradou,nrimovel,nrquadra,nrlote,nmbairro,ci,x_coord,y_coord",
        )

    def _query_lot_by_parcel(self, evidence: LocationEvidence) -> list[dict]:
        """Find cadastral lots from neighborhood + block + lot evidence."""
        if not evidence.neighborhood or not evidence.quadra or not evidence.lote:
            return []

        neighborhood_features = self._query_layer_where(
            NEIGHBORHOOD_LAYER_ID,
            f"nm_bai LIKE '%{_escape_where_value(evidence.neighborhood)}%'",
            "id,nm_bai",
        )
        if not neighborhood_features:
            neighborhood_name = re.sub(
                r"^(setor|s)\s+",
                "",
                evidence.neighborhood.strip(),
                flags=re.IGNORECASE,
            )
            if neighborhood_name != evidence.neighborhood.strip():
                neighborhood_features = self._query_layer_where(
                    NEIGHBORHOOD_LAYER_ID,
                    f"nm_bai LIKE '%{_escape_where_value(neighborhood_name)}%'",
                    "id,nm_bai",
                )

        if not neighborhood_features:
            return []

        neighborhood_id = (neighborhood_features[0].get("attributes") or {}).get("id")
        if not neighborhood_id:
            return []

        block_features = self._query_layer_where(
            BLOCK_LAYER_ID,
            (
                f"id_bai = '{_escape_where_value(neighborhood_id)}' "
                f"AND nm_qdr LIKE '%{_escape_where_value(evidence.quadra)}%'"
            ),
            "id,nm_qdr,id_bai",
        )
        if not block_features:
            return []

        block_id = (block_features[0].get("attributes") or {}).get("id")
        if not block_id:
            return []

        return self._query_layer_where(
            LOT_LAYER_ID,
            (
                f"id_qdr = '{_escape_where_value(block_id)}' "
                f"AND nm_lot = '{_escape_where_value(evidence.lote)}'"
            ),
            "id,id_qdr,nm_lot,nm_imovel,id_seg",
        )

    def _query_layer_where(self, layer_id: int, where: str, out_fields: str) -> list[dict]:
        params = {
            "where": where,
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

    def _query_official_numbers(self, evidence: LocationEvidence) -> list[dict]:
        return self._query_layer_at_point(
            evidence.latitude,
            evidence.longitude,
            OFFICIAL_NUMBER_LAYER_ID,
            "id,nm_npo,cd_log,cd_rua,cd_bai,ci",
        )

    def _query_street_segments(self, latitude: float, longitude: float) -> list[dict]:
        return self._query_layer_at_point(latitude, longitude, STREET_SEGMENT_LAYER_ID, "id_seg,cd_log,cd_rua")

    def _nearest_street_access(self, property_point: tuple[float, float]) -> tuple[float, float] | None:
        """Find the nearest street candidate around the resolved property point."""
        longitude, latitude = property_point
        segments = self._query_street_segments(latitude, longitude)
        best: tuple[float, tuple[float, float]] | None = None
        for feature in segments:
            for path in (feature.get("geometry") or {}).get("paths") or []:
                for start, end in zip(path, path[1:]):
                    candidate = _nearest_point_on_segment(property_point, start, end)
                    distance = (candidate[0] - property_point[0]) ** 2 + (candidate[1] - property_point[1]) ** 2
                    if best is None or distance < best[0]:
                        best = (distance, candidate)
        return best[1] if best is not None else None

    def _query_layer_at_point(self, latitude: float, longitude: float, layer_id: int, out_fields: str) -> list[dict]:
        delta = 0.0005
        params = {
            "where": "1=1",
            "geometry": f"{longitude - delta},{latitude - delta},{longitude + delta},{latitude + delta}",
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


def _escape_where_value(value: object) -> str:
    return str(value).replace("'", "''")


def _resolution_cache_key(evidence: LocationEvidence) -> tuple[object, ...]:
    return (
        evidence.latitude,
        evidence.longitude,
        evidence.normalized_address,
        evidence.number,
        evidence.quadra,
        evidence.lote,
        evidence.zipcode,
        evidence.neighborhood,
        evidence.city,
    )


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _normalize_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text or None


def _same_normalized_value(left: object, right: object) -> bool:
    left_normalized = _normalize_number(left)
    right_normalized = _normalize_number(right)
    return left_normalized is not None and left_normalized == right_normalized


def _same_street_name(cadastral_name: object, normalized_address: object) -> bool:
    street = _normalize_text(cadastral_name)
    address = _normalize_text(normalized_address)
    if not street or not address:
        return False
    return street in address or address in street


def _best_matching_cadastral_record(evidence: LocationEvidence, features: list[dict]) -> dict | None:
    if not features:
        return None

    target_neighborhood = _normalize_text(evidence.neighborhood)
    target_number = _normalize_number(evidence.number)
    best: tuple[float, dict] | None = None
    for feature in features:
        attributes = feature.get("attributes") or {}
        score = 0.0
        if _same_normalized_value(attributes.get("nrquadra"), evidence.quadra):
            score += 4.0
        if _same_normalized_value(attributes.get("nrlote"), evidence.lote):
            score += 5.0
        if target_neighborhood and _normalize_text(attributes.get("nmbairro")) == target_neighborhood:
            score += 4.0
        if target_number and _same_normalized_value(attributes.get("nrimovel"), target_number):
            score += 5.0
        if _same_street_name(attributes.get("nmlogradou"), evidence.normalized_address):
            score += 3.0
        if evidence.latitude is not None and evidence.longitude is not None:
            score += max(0.0, 2.0 - min(2.0, _distance_sq_to_geometry(evidence, feature.get("geometry") or {}) * 1e8))
        candidate = (score, feature)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best is not None and best[0] >= 9.0 else None


def _resolved_with_access(
    property_point: tuple[float, float],
    access_point: tuple[float, float] | None,
    *,
    confidence: float,
    source: str,
    cadastral_id: object,
) -> ResolvedLocation:
    route_point = access_point or property_point
    return ResolvedLocation(
        latitude=route_point[1],
        longitude=route_point[0],
        confidence=confidence,
        source=source,
        property_latitude=property_point[1],
        property_longitude=property_point[0],
        access_latitude=access_point[1] if access_point is not None else None,
        access_longitude=access_point[0] if access_point is not None else None,
        cadastral_id=str(cadastral_id) if cadastral_id is not None else None,
    )


def _cadastral_coordinate_point(attributes: dict) -> tuple[float, float] | None:
    x = attributes.get("x_coord")
    y = attributes.get("y_coord")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        # Cadastro coordinates are longitude/latitude in the requested 4326 output.
        if -180 <= float(x) <= 180 and -90 <= float(y) <= 90:
            return float(x), float(y)
    return None


def _point_from_geometry(geometry: dict) -> tuple[float, float] | None:
    x = geometry.get("x")
    y = geometry.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def _best_matching_official_number(evidence: LocationEvidence, features: list[dict]) -> dict | None:
    target = _normalize_number(evidence.number)
    if target is None:
        return None
    matches = []
    for feature in features:
        attributes = feature.get("attributes") or {}
        if _normalize_number(attributes.get("nm_npo")) == target:
            matches.append(feature)
    if not matches:
        return None
    return min(matches, key=lambda feature: _distance_sq_to_geometry(evidence, feature.get("geometry") or {}))


def _representative_point(geometry: dict) -> tuple[float, float] | None:
    rings = geometry.get("rings")
    if not rings or not rings[0] or len(rings[0]) < 3:
        return None
    points = rings[0]
    area_twice = cx = cy = 0.0
    for current, nxt in zip(points, points[1:] + points[:1]):
        cross = current[0] * nxt[1] - nxt[0] * current[1]
        area_twice += cross
        cx += (current[0] + nxt[0]) * cross
        cy += (current[1] + nxt[1]) * cross
    if abs(area_twice) < 1e-12:
        return points[0][0], points[0][1]
    return cx / (3 * area_twice), cy / (3 * area_twice)


def _nearest_point_on_segment(
    point: tuple[float, float], start: list[float], end: list[float]
) -> tuple[float, float]:
    px, py = point
    x1, y1 = float(start[0]), float(start[1])
    x2, y2 = float(end[0]), float(end[1])
    dx, dy = x2 - x1, y2 - y1
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / denominator
    t = max(0.0, min(1.0, t))
    return x1 + t * dx, y1 + t * dy


def _distance_sq_to_geometry(evidence: LocationEvidence, geometry: dict) -> float:
    point = _point_from_geometry(geometry) or _representative_point(geometry)
    if point is None:
        return float("inf")
    if evidence.longitude is None or evidence.latitude is None:
        return float("inf")
    return (point[0] - evidence.longitude) ** 2 + (point[1] - evidence.latitude) ** 2
