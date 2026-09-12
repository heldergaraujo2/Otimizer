# Otimizer

Route optimization platform for delivery operations.

## Vision

Import delivery spreadsheets (`.xlsx`), detect every delivery with valid latitude and longitude, reconstruct physical stops independently of the source `Sequence`/`Stop`, optimize the driving order using real road-network travel costs, and provide a numbered interactive map with stop details and navigation to the next stop.

The product is web-first during development, with a mobile delivery experience as a first-class target.

## Non-negotiable rules

1. Every spreadsheet row with valid latitude and longitude must be represented in the resulting route.
2. Existing `Sequence`/`Stop` values are reference data, not a reason to exclude an eligible delivery or blindly define physical stops.
3. Multiple deliveries at the same physical location remain linked to one physical stop while preserving every delivery/order/package record.
4. Different physical locations remain separate stops, even if the source `Stop` value is identical.
5. Route cost uses the real road network and driving directionality, not straight-line distance alone.
6. Every generated physical stop receives a unique route sequence number.
7. The UI must clearly show imported deliveries, physical stops, routed stops, and unresolved rows.
8. Mobile navigation is a first-class product target.

## Processing pipeline

XLSX → import → validate → normalize → identify deliveries → reconstruct physical stops → road-network costs → optimize → generate route sequence → numbered map → stop details → next-stop navigation.

## Project status

Foundation phase. Requirements and architecture are being formalized before implementation of the importer and routing engine.

## Privacy

Real delivery spreadsheets may contain addresses and tracking identifiers. Do not publish raw customer data in public repositories or fixtures without explicit authorization. Prefer anonymized test fixtures when possible.
