# Validation notes

Prepared: 2026-11-02.

## Executed checks

- Fresh hub analysis using the local March 2026 yellow taxi file: completed with 3,051,915 retained trips and a top-50 hub-pair demand share of 85.9831%.
- Offline assignment regression: overlapping cheap request groups cannot duplicate a request.
- Offline route-metric regression: distance and duration follow the same minimum-time parallel edge.
- Tiny two-request simulation: door-to-door and walking scenarios both respect checked service bounds and produce unique request records.
- Archive validation: preserved hashes match; mean request-level waiting, walking, and delay agree with the saved summary.
- English archived comparison figure regenerated from the preserved summary CSV.

The full corrected dynamic assignment was not rerun on the TLC dataset. The optional live OSM download and fresh road-path analysis were not executed. Neither the archived assignment outcome nor the old route metrics are validated by the small regression tests.

## Checked environment

Python 3.14.6.

| Package | Version |
| --- | --- |
| pandas | 3.1.0 |
| numpy | 2.5.4 |
| geopandas | 1.2.0 |
| shapely | 2.2.0 |
| scikit-learn | 1.9.1 |
| pyarrow | 26.0.0 |
| matplotlib | 3.11.2 |
| osmnx | 2.1.1 |
| networkx | 3.7 |
| scipy | 1.18.1 |
| pulp | 4.2.0 |
| tqdm | 4.70.1 |

The dependency ranges in `requirements.txt` are broader than this one checked environment. PuLP is bounded below version 4 because this prototype uses its bundled CBC interface. Exact coordinates can change with library or input revisions.
