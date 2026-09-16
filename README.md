# Otimizer

Route optimization platform for delivery operations.

## Vision

Import delivery spreadsheets (`.xlsx`), preserve every delivery row, reconstruct physical stops independently of the source `Sequence`/`Stop`, cross-check GPS with address and cadastral evidence such as quadra/lote when available, optimize the driving order using real road-network travel costs, and provide a numbered interactive map with stop details and navigation.

The product is web-first during development, with a mobile delivery experience as a first-class target.

## Non-negotiable rules

1. Every valid delivery row must remain represented in the resulting route, even when coordinates are missing or unusable.
2. Missing location data must degrade to a lower-confidence location, an approximate point, or a pending stop; it must never silently drop the delivery or abort optimization of the rest of the route.
3. Existing `Sequence`/`Stop` values are reference data, not a reason to exclude an eligible delivery or blindly define physical stops.
4. Multiple deliveries at the same physical location remain linked to one physical stop while preserving every delivery/order/package record.
5. Different physical locations remain separate stops, even if the source `Stop` value is identical.
6. Route cost uses the real road network and driving directionality, not straight-line distance alone.
7. Every generated physical stop receives a unique route sequence number.
8. The UI must clearly show imported deliveries, physical stops, routed stops, and unresolved rows.
9. A pending or approximate stop can be manually placed on the map by the driver; confirmation triggers a full-route reoptimization while preserving the original delivery evidence.
10. Mobile navigation is a first-class product target.

## Processing pipeline

XLSX → import → validate → normalize → identify deliveries → reconstruct physical stops → cadastral/GPS evidence → resolve exact/access/approximate/pending location → road-network costs → optimize → generate route sequence → numbered map → stop details → manual map correction when necessary → full route reoptimization → next-stop navigation.

## Project status

Core importer, resilient physical-stop reconstruction, road-network routing, route optimization, authenticated API, licensing foundation, and frontend route-safety flow are implemented. The current validation phase focuses on real XLSX route imports, cadastral resolution, partial-routing resilience, and manual recovery of unresolved stops.

## Privacy

Real delivery spreadsheets may contain addresses and tracking identifiers. Do not publish raw customer data in public repositories or fixtures without explicit authorization. Prefer anonymized test fixtures when possible.
