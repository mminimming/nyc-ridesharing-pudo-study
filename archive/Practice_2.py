# pip install pandas geopandas scikit-learn pyarrow shapely matplotlib osmnx networkx

import pandas as pd
import geopandas as gpd
from sklearn.cluster import KMeans
from pathlib import Path
import matplotlib.pyplot as plt
import osmnx as ox
import networkx as nx
# =========================
# 0. 파일 경로 설정
# =========================

DATA_DIR = Path(".")

TRIP_FILES = [
    DATA_DIR / "yellow_tripdata_2026-03.parquet",
]

ZONE_LOOKUP = DATA_DIR / "taxi_zone_lookup.csv"

ZONE_SHP = (
    DATA_DIR
    / "taxi_zones 2"
    / "taxi_zones.shp"
)

N_PICKUP_HUBS = 10
N_DROPOFF_HUBS = 10

TOP_ROUTES = 50
FIGSIZE = (10, 10)
USE_ROAD_NETWORK = True
OSM_PLACE_NAME = "Manhattan, New York City, New York, USA"
# =========================
# Load road network graph
# =========================
def load_road_graph():
    print("Downloading Manhattan road network from OpenStreetMap...")
    G = ox.graph_from_place(
        OSM_PLACE_NAME,
        network_type="drive",
        simplify=True
    )

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    print(f"Road graph loaded: {len(G.nodes):,} nodes, {len(G.edges):,} edges")
    return G



# =========================
# 1. taxi zone shapefile 준비
# =========================


# =========================
# 2. Zone centroid 만들기
# =========================
def load_zones():
    zones = gpd.read_file(ZONE_SHP)
    zones = zones.to_crs(epsg=4326)

    lookup = pd.read_csv(ZONE_LOOKUP)

    zones = zones.merge(
        lookup,
        on="LocationID",
        how="left"
    )

    zones["centroid"] = zones.geometry.centroid
    zones["lon"] = zones["centroid"].x
    zones["lat"] = zones["centroid"].y

    zones = zones[
        ["LocationID", "Borough", "Zone", "lon", "lat", "geometry"]
    ].copy()

    return zones


# =========================
# 3. TLC OD 수요 읽기
# =========================

def load_trips():
    dfs = []

    for f in TRIP_FILES:
        print(f"Reading {f.name} ...")
        df = pd.read_parquet(
            f,
            columns=[
                "tpep_pickup_datetime",
                "tpep_dropoff_datetime",
                "PULocationID",
                "DOLocationID",
                "passenger_count",
                "trip_distance",
            ]
        )
        dfs.append(df)

    trips = pd.concat(dfs, ignore_index=True)

    trips = trips[
        (trips["passenger_count"].fillna(1) > 0) &
        (trips["trip_distance"] > 0) &
        trips["PULocationID"].notna() &
        trips["DOLocationID"].notna()
    ].copy()

    trips["PULocationID"] = trips["PULocationID"].astype(int)
    trips["DOLocationID"] = trips["DOLocationID"].astype(int)

    return trips


# =========================
# 4. Manhattan OD만 필터링
# =========================

def attach_zone_info(trips, zones):
    pu = zones[["LocationID", "Borough", "Zone", "lon", "lat"]].rename(
        columns={
            "LocationID": "PULocationID",
            "Borough": "PU_Borough",
            "Zone": "PU_Zone",
            "lon": "PU_lon",
            "lat": "PU_lat",
        }
    )

    do = zones[["LocationID", "Borough", "Zone", "lon", "lat"]].rename(
        columns={
            "LocationID": "DOLocationID",
            "Borough": "DO_Borough",
            "Zone": "DO_Zone",
            "lon": "DO_lon",
            "lat": "DO_lat",
        }
    )

    trips = trips.merge(pu, on="PULocationID", how="left")
    trips = trips.merge(do, on="DOLocationID", how="left")

    trips = trips[
        (trips["PU_Borough"] == "Manhattan") &
        (trips["DO_Borough"] == "Manhattan")
    ].copy()

    return trips


# =========================
# 5. Pickup / Dropoff hub clustering
# =========================

def make_weighted_points(trips, lon_col, lat_col):
    points = trips[[lon_col, lat_col]].dropna().copy()
    return points.values


def assign_hubs(trips):
    pickup_points = make_weighted_points(trips, "PU_lon", "PU_lat")
    dropoff_points = make_weighted_points(trips, "DO_lon", "DO_lat")

    pickup_kmeans = KMeans(
        n_clusters=N_PICKUP_HUBS,
        random_state=42,
        n_init="auto"
    )
    dropoff_kmeans = KMeans(
        n_clusters=N_DROPOFF_HUBS,
        random_state=42,
        n_init="auto"
    )

    trips["pickup_hub"] = pickup_kmeans.fit_predict(
        trips[["PU_lon", "PU_lat"]]
    )

    trips["dropoff_hub"] = dropoff_kmeans.fit_predict(
        trips[["DO_lon", "DO_lat"]]
    )

    pickup_hubs = pd.DataFrame(
        pickup_kmeans.cluster_centers_,
        columns=["lon", "lat"]
    )
    pickup_hubs["hub_id"] = pickup_hubs.index
    pickup_hubs["type"] = "pickup"

    dropoff_hubs = pd.DataFrame(
        dropoff_kmeans.cluster_centers_,
        columns=["lon", "lat"]
    )
    dropoff_hubs["hub_id"] = dropoff_hubs.index
    dropoff_hubs["type"] = "dropoff"

    return trips, pickup_hubs, dropoff_hubs


# =========================
# 6. Hub-to-hub OD matrix 만들기
# =========================

def make_hub_od_matrix(trips):
    od = (
        trips
        .groupby(["pickup_hub", "dropoff_hub"])
        .size()
        .reset_index(name="demand")
        .sort_values("demand", ascending=False)
    )

    return od


# =========================
# 7. Route 후보 생성
# =========================

def make_route_candidates(od, pickup_hubs, dropoff_hubs):
    routes = od.head(TOP_ROUTES).copy()

    routes = routes.merge(
        pickup_hubs[["hub_id", "lon", "lat"]],
        left_on="pickup_hub",
        right_on="hub_id",
        how="left"
    ).rename(columns={
        "lon": "pickup_hub_lon",
        "lat": "pickup_hub_lat",
    }).drop(columns=["hub_id"])

    routes = routes.merge(
        dropoff_hubs[["hub_id", "lon", "lat"]],
        left_on="dropoff_hub",
        right_on="hub_id",
        how="left"
    ).rename(columns={
        "lon": "dropoff_hub_lon",
        "lat": "dropoff_hub_lat",
    }).drop(columns=["hub_id"])

    return routes


# =========================
# Add road network paths to route candidates
# =========================
def add_road_paths_to_routes(G, routes):
    routes = routes.copy()

    pickup_nodes = ox.distance.nearest_nodes(
        G,
        routes["pickup_hub_lon"],
        routes["pickup_hub_lat"]
    )
    dropoff_nodes = ox.distance.nearest_nodes(
        G,
        routes["dropoff_hub_lon"],
        routes["dropoff_hub_lat"]
    )

    road_path_nodes = []
    road_distance_m = []
    road_travel_time_sec = []

    for pu_node, do_node in zip(pickup_nodes, dropoff_nodes):
        try:
            path = nx.shortest_path(
                G,
                pu_node,
                do_node,
                weight="travel_time"
            )

            distance = nx.shortest_path_length(
                G,
                pu_node,
                do_node,
                weight="length"
            )

            travel_time = nx.shortest_path_length(
                G,
                pu_node,
                do_node,
                weight="travel_time"
            )

        except nx.NetworkXNoPath:
            path = []
            distance = None
            travel_time = None

        road_path_nodes.append(path)
        road_distance_m.append(distance)
        road_travel_time_sec.append(travel_time)

    routes["pickup_road_node"] = pickup_nodes
    routes["dropoff_road_node"] = dropoff_nodes
    routes["road_path_nodes"] = road_path_nodes
    routes["road_distance_m"] = road_distance_m
    routes["road_travel_time_sec"] = road_travel_time_sec
    routes["road_travel_time_min"] = routes["road_travel_time_sec"] / 60

    return routes


# =========================
# 7b. Visualization Function
# =========================
def visualize_original_demand(zones, trips):
    fig, ax = plt.subplots(figsize=FIGSIZE)

    manhattan = zones[zones["Borough"] == "Manhattan"]
    manhattan.plot(
        ax=ax,
        color="white",
        edgecolor="black",
        linewidth=0.5,
        alpha=0.7
    )

    # pickup demand points
    ax.scatter(
        trips["PU_lon"],
        trips["PU_lat"],
        s=3,
        alpha=0.15,
        label="Pickup demand"
    )

    # dropoff demand points
    ax.scatter(
        trips["DO_lon"],
        trips["DO_lat"],
        s=3,
        alpha=0.15,
        marker="x",
        label="Dropoff demand"
    )

    ax.set_title("Original Manhattan OD Demand Distribution")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend()

    plt.tight_layout()
    plt.savefig("original_od_demand_distribution.png", dpi=300)
    plt.show()

def visualize_zone_demand(zones, trips):
    pickup_counts = (
        trips
        .groupby("PULocationID")
        .size()
        .reset_index(name="pickup_demand")
    )

    dropoff_counts = (
        trips
        .groupby("DOLocationID")
        .size()
        .reset_index(name="dropoff_demand")
    )

    pickup_map = zones.merge(
        pickup_counts,
        left_on="LocationID",
        right_on="PULocationID",
        how="left"
    )
    pickup_map["pickup_demand"] = pickup_map["pickup_demand"].fillna(0)
    pickup_map = pickup_map[pickup_map["Borough"] == "Manhattan"]

    dropoff_map = zones.merge(
        dropoff_counts,
        left_on="LocationID",
        right_on="DOLocationID",
        how="left"
    )
    dropoff_map["dropoff_demand"] = dropoff_map["dropoff_demand"].fillna(0)
    dropoff_map = dropoff_map[dropoff_map["Borough"] == "Manhattan"]

    fig, ax = plt.subplots(figsize=FIGSIZE)
    pickup_map.plot(
        ax=ax,
        column="pickup_demand",
        legend=True,
        edgecolor="black",
        linewidth=0.3
    )
    ax.set_title("Pickup Demand by Taxi Zone")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    plt.savefig("pickup_demand_by_zone.png", dpi=300)
    plt.show()

    fig, ax = plt.subplots(figsize=FIGSIZE)
    dropoff_map.plot(
        ax=ax,
        column="dropoff_demand",
        legend=True,
        edgecolor="black",
        linewidth=0.3
    )
    ax.set_title("Dropoff Demand by Taxi Zone")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()
    plt.savefig("dropoff_demand_by_zone.png", dpi=300)
    plt.show()

def visualize_routes(zones, pickup_hubs, dropoff_hubs, routes):
    fig, ax = plt.subplots(figsize=FIGSIZE)

    # Manhattan zone boundary
    manhattan = zones[zones["Borough"] == "Manhattan"]
    manhattan.plot(
        ax=ax,
        color="white",
        edgecolor="black",
        linewidth=0.5,
        alpha=0.7
    )

    # pickup hubs
    ax.scatter(
        pickup_hubs["lon"],
        pickup_hubs["lat"],
        s=120,
        label="Pickup Hubs"
    )

    # dropoff hubs
    ax.scatter(
        dropoff_hubs["lon"],
        dropoff_hubs["lat"],
        s=120,
        marker="x",
        label="Dropoff Hubs"
    )

    # route lines
    for _, row in routes.iterrows():
        ax.plot(
            [row["pickup_hub_lon"], row["dropoff_hub_lon"]],
            [row["pickup_hub_lat"], row["dropoff_hub_lat"]],
            linewidth=max(row["demand"] / routes["demand"].max() * 5, 0.5),
            alpha=0.7
        )

    # label pickup hubs
    for _, row in pickup_hubs.iterrows():
        ax.text(
            row["lon"],
            row["lat"],
            f"P{row['hub_id']}",
            fontsize=8
        )

    # label dropoff hubs
    for _, row in dropoff_hubs.iterrows():
        ax.text(
            row["lon"],
            row["lat"],
            f"D{row['hub_id']}",
            fontsize=8
        )

    ax.set_title("Manhattan Demand Hub Routes")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend()

    plt.tight_layout()
    plt.savefig("manhattan_hub_routes.png", dpi=300)
    plt.show()


# =========================
# Visualize routes on road network
# =========================
def visualize_road_routes(G, zones, pickup_hubs, dropoff_hubs, routes):
    fig, ax = plt.subplots(figsize=FIGSIZE)

    manhattan = zones[zones["Borough"] == "Manhattan"]
    manhattan.plot(
        ax=ax,
        color="white",
        edgecolor="black",
        linewidth=0.5,
        alpha=0.7
    )

    ox.plot_graph_routes(
        G,
        routes["road_path_nodes"].tolist(),
        route_linewidths=[
            max(demand / routes["demand"].max() * 4, 0.5)
            for demand in routes["demand"]
        ],
        route_alpha=0.75,
        node_size=0,
        edge_linewidth=0.2,
        edge_alpha=0.2,
        bgcolor="white",
        show=False,
        close=False,
        ax=ax
    )

    ax.scatter(
        pickup_hubs["lon"],
        pickup_hubs["lat"],
        s=120,
        label="Pickup Hubs"
    )

    ax.scatter(
        dropoff_hubs["lon"],
        dropoff_hubs["lat"],
        s=120,
        marker="x",
        label="Dropoff Hubs"
    )

    for _, row in pickup_hubs.iterrows():
        ax.text(row["lon"], row["lat"], f"P{row['hub_id']}", fontsize=8)

    for _, row in dropoff_hubs.iterrows():
        ax.text(row["lon"], row["lat"], f"D{row['hub_id']}", fontsize=8)

    ax.set_title("Manhattan Demand Hub Routes on Road Network")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend()

    plt.tight_layout()
    plt.savefig("manhattan_hub_road_routes.png", dpi=300)
    plt.show()


# =========================
# 8. 실행
# =========================

def main():
    zones = load_zones()
    G = load_road_graph() if USE_ROAD_NETWORK else None
    trips = load_trips()
    trips = attach_zone_info(trips, zones)

    print(f"Manhattan OD trips: {len(trips):,}")
    visualize_original_demand(zones, trips)
    visualize_zone_demand(zones, trips)

    trips, pickup_hubs, dropoff_hubs = assign_hubs(trips)

    od = make_hub_od_matrix(trips)
    routes = make_route_candidates(od, pickup_hubs, dropoff_hubs)
    if USE_ROAD_NETWORK:
        routes = add_road_paths_to_routes(G, routes)

    pickup_hubs.to_csv("pickup_hubs.csv", index=False)
    dropoff_hubs.to_csv("dropoff_hubs.csv", index=False)
    od.to_csv("hub_od_matrix.csv", index=False)
    routes.to_csv("route_candidates.csv", index=False)

    visualize_routes(
        zones,
        pickup_hubs,
        dropoff_hubs,
        routes
    )
    if USE_ROAD_NETWORK:
        visualize_road_routes(
            G,
            zones,
            pickup_hubs,
            dropoff_hubs,
            routes
        )

    print("\n===== Top Route Candidates =====")
    print(routes)

    print("\nSaved files:")
    print("- pickup_hubs.csv")
    print("- dropoff_hubs.csv")
    print("- hub_od_matrix.csv")
    print("- route_candidates.csv")
    print("- manhattan_hub_routes.png")
    print("- original_od_demand_distribution.png")
    print("- pickup_demand_by_zone.png")
    print("- dropoff_demand_by_zone.png")
    if USE_ROAD_NETWORK:
        print("- manhattan_hub_road_routes.png")


if __name__ == "__main__":
    main()