# Data preparation

Download the following from the official [NYC TLC Trip Record Data page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page):

1. March 2026 **Yellow Taxi Trip Records**, in Parquet format.
2. **Taxi Zone Lookup Table**, in CSV format.
3. **Taxi Zone Shapefile**, extracted with all companion files.

Arrange the local inputs as follows:

```text
data/raw/
  yellow_tripdata_2026-03.parquet
  taxi_zone_lookup.csv
  taxi_zones/
    taxi_zones.shp
    taxi_zones.dbf
    taxi_zones.shx
    taxi_zones.prj
    taxi_zones.cpg
```

These inputs are not bundled with the repository. Do not commit raw Parquet, shapefile downloads, or network caches. Use the source providers' terms when obtaining or redistributing data.

The hub analysis reads pickup/drop-off zone IDs, passenger count, and trip distance. The dynamic experiment also reads pickup times to create its request stream. Modern trip records identify taxi zones, not exact passenger locations: both experiments use zone centroids as spatial proxies.

The fresh hub run used the March 2026 file with SHA-256:

```text
d7af794a7ac06cbbb5afb4d1df9e86d84f2e878584de708ff2ffca4bd7d234d9
```

A later provider revision may produce a different hash or result. The complete run manifest is in `results/hub_analysis/run.json`.

Road routing is optional for the hub exercise. Use an OSMnx drive graph with geographic node coordinates and `length` (meters) and `travel_time` (seconds) on every edge. `--road-network` builds one using OSMnx speed estimates, with a 30 km/h fallback. These are modeled travel times, not live traffic observations. Dynamic assignment downloads the same kind of graph unless a snapshot is supplied.

For repeatable network experiments, save and reuse the same GraphML snapshot. OpenStreetMap data are © OpenStreetMap contributors; see [copyright and licensing](https://www.openstreetmap.org/copyright).
