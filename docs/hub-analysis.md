# Demand-weighted hub analysis

## Question and method

Where are Manhattan taxi origins and destinations concentrated, and how much observed demand lies between the most frequent hub pairs?

The cleaned script filters yellow taxi trips to Manhattan-to-Manhattan movements with positive trip distance and passenger count. Missing passenger count is treated as one for filtering. Each retained trip contributes one unit of demand, regardless of its passenger count. Pickup and drop-off demand are aggregated by taxi zone.

Taxi-zone centroids and clustering coordinates use **EPSG:2263**, a projected coordinate system whose units are US survey feet. Separate demand-weighted KMeans models create 10 pickup hubs and 10 drop-off hubs (`random_state=42`, `n_init=10`). Zone-to-zone counts are mapped to hub pairs and summed. The highest-demand 50 pairs are retained as route candidates.

## Fresh result

| Item | Value |
| --- | ---: |
| Input | March 2026 yellow taxi records |
| Retained trips | 3,051,915 |
| Pickup hubs / drop-off hubs | 10 / 10 |
| Selected hub pairs | 50 |
| Demand share of selected pairs | 85.98% |

The run manifest records the seed, coordinate system, taxi input hash, and script hash. CSVs contain aggregated demand, hub coordinates, and route candidates. This is a descriptive demand analysis, not a vehicle-routing or fleet-assignment solution.

## Current and archived maps

`results/hub_analysis/zone-demand.png` and `hub-connections.png` come from the fresh projected-coordinate run. Connection lines represent demand relationships, not driven paths. A statistical center can fall outside a usable boarding location or even outside a road segment.

The original Practice 2 outputs remain in `results/archived/hub_analysis/` and `figures/archived/`. The old clustering used geographic longitude/latitude coordinates. Its 50 selected pairs contain 2,550,570 trips, or approximately 83.57% of its 3,051,915 retained trips. The updated projected clustering intentionally changes hub positions and memberships, so its demand share is different.

The archived road map depicts the old hub layout. Historical route distance and travel-time fields were optimized using different edge weights and should not be interpreted as measurements of the same route. The cleaned `path_metrics` function measures both length and time along the chosen minimum-time path, including the same selected parallel edge. This is covered by a regression test.

## Optional road paths

Use `--graph-file` with a saved OSMnx drive graph, or `--road-network` to download one. Hub centers are snapped to nearest road nodes; minimum-time paths are computed on the directed drive graph. An unreachable pair receives an empty path and missing metrics. The fresh committed run did not execute this optional network step.

## Limits

Zone centroids collapse within-zone variation. KMeans minimizes weighted squared coordinate distance, not walking distance, driving time, or boarding inconvenience. Hubs are statistical summaries rather than proposed legal pickup facilities. Monthly counts hide variation by hour and day. No demand uncertainty, transit access, transfer behavior, fleet constraints, or passenger acceptance is modeled.
