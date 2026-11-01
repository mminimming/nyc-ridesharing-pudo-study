# Dynamic assignment experiment

## Question and method

Can allowing passengers to walk to nearby pickup/drop-off nodes change assignment costs and service outcomes in a small ridesharing prototype?

Taxi-zone centroids are snapped to a Manhattan drive graph. A request contains its time, origin, destination, passenger count, and direct driving time. At each batch, the model considers idle vehicles and enumerates small request groups. It searches pickup/drop-off candidates and pickup-before-drop-off service sequences, enforces walking/waiting/delay/capacity bounds, and retains a feasible minimum-cost edge for each group–vehicle combination.

The binary optimization chooses edges and rejection indicators. Each request is assigned **exactly once or rejected**, and each available vehicle receives at most one group. Assignment costs combine passenger time terms and vehicle service time; the model also penalizes rejection.

## Changes from the original practice script

- Corrected request coverage from `>= 1` to `== 1`. Overlapping groups can otherwise serve the same request twice. An adversarial regression test covers this case.
- Added a post-solve duplicate-assignment check.
- Made file paths portable and added CLI graph loading/saving and a shared random seed.
- Added sampled-request CSV and run-manifest output.
- Updated network preprocessing to OSMnx's routing namespace.

Original code and results remain unchanged under `archive/` and `results/archived/`. Fixing the implementation does not retroactively validate the archived figures.

## Interpreting the historical comparison

Both archived CSVs contain 98 accepted request IDs and no rejections. Recomputed row-level mean waiting, walking, and arrival delay agree with the archived summary. Fleet state is not present in the request CSVs, so total vehicle time can only be read from the preserved summary.

| Metric | Definition in this implementation |
| --- | --- |
| Waiting | Pickup time minus request time and origin walking time; excludes the origin walk |
| Walking | Origin-to-pickup plus drop-off-to-destination walking time |
| Arrival delay | Destination arrival including destination walking, minus request time and direct driving time |
| Vehicle service time (`vht_hours`) | Sum of assigned vehicle tour durations, including passenger-readiness waiting |
| Walk share | Fraction of accepted requests with positive total walking |

The historical fleet size, actual request window, full parameter set, solver environment, and graph snapshot were not saved. Defaults in the original script are not evidence of the arguments used. The saved comparison is therefore a descriptive archival result, without confidence intervals or a claim that walking generally improves service.

## Model limits

- Only idle vehicles receive new groups. Busy vehicles are not revisited, and active passenger itineraries are not dynamically reoptimized.
- Taxi-zone centroids are coarse demand proxies. Actual passenger origins and destinations are unknown.
- The walking graph is an undirected transformation of the drive graph. It is not a pedestrian-accessibility network and may miss or misrepresent walkable links.
- The walking limit applies separately at the origin and destination; total walking may reach twice the configured limit.
- Small-group enumeration and limited candidate nodes restrict the search. There is no guarantee of a globally optimal service plan over the full horizon.
- Requests left pending at the last request batch are rejected when the simulation ends. The model does not extend the horizon to wait for every busy vehicle to return.
- Congestion, live traffic, operational dwell times, and street-level pickup suitability are not modeled.

This is an exercise inspired by [Fielbaum et al. (2021)](https://doi.org/10.1016/j.trc.2021.103061), not an implementation-equivalent reproduction of that study.
