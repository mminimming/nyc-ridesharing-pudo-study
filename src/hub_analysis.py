"""Demand-weighted Manhattan hub analysis using zone-level TLC origins/destinations."""
from pathlib import Path
import argparse
import hashlib
import json
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point
from sklearn.cluster import KMeans

ROOT=Path(__file__).resolve().parents[1]

def load_zones(shp, lookup):
    zones=gpd.read_file(shp)[['LocationID','geometry']]
    if zones.crs is None: raise ValueError('Taxi-zone CRS is missing.')
    meta=pd.read_csv(lookup)[['LocationID','Borough','Zone']]
    zones=zones.merge(meta,on='LocationID',validate='one_to_one')
    zones=zones[zones.Borough.str.strip().eq('Manhattan')].copy().to_crs(2263)
    zones['x']=zones.geometry.centroid.x
    zones['y']=zones.geometry.centroid.y
    return zones

def load_od(files, valid_ids):
    batches=[]
    for file in files:
        df=pd.read_parquet(file,columns=['PULocationID','DOLocationID','passenger_count','trip_distance'])
        keep=(df.passenger_count.fillna(1)>0)&(df.trip_distance>0)&df.PULocationID.isin(valid_ids)&df.DOLocationID.isin(valid_ids)
        grouped=df.loc[keep].groupby(['PULocationID','DOLocationID']).size().rename('demand').reset_index()
        batches.append(grouped)
    return pd.concat(batches).groupby(['PULocationID','DOLocationID'],as_index=False).demand.sum()

def cluster_hubs(zones, counts, k, seed, kind):
    active=zones.merge(counts.rename('demand'),left_on='LocationID',right_index=True,validate='one_to_one')
    active=active[active.demand>0].copy()
    if not 1<=k<=len(active): raise ValueError('Hub count must not exceed active taxi zones.')
    model=KMeans(n_clusters=k,random_state=seed,n_init=10)
    active['hub_id']=model.fit_predict(active[['x','y']],sample_weight=active.demand.to_numpy())
    centers=gpd.GeoSeries([Point(x,y) for x,y in model.cluster_centers_],crs=2263).to_crs(4326)
    hubs=pd.DataFrame({'hub_id':range(k),'lon':centers.x,'lat':centers.y,'type':kind})
    return active[['LocationID','hub_id']],hubs

def path_metrics(graph, path):
    """Measure length and time on the same selected minimum-time multiedges."""
    distance=duration=0.0
    for a,b in zip(path,path[1:]):
        edges=list(graph.get_edge_data(a,b).values()) if graph.is_multigraph() else [graph[a][b]]
        chosen=min(edges,key=lambda e:(float(e['travel_time']),float(e['length'])))
        distance+=float(chosen['length']);duration+=float(chosen['travel_time'])
    return distance,duration

def add_road_paths(graph,routes):
    routes=routes.copy()
    pu=ox.distance.nearest_nodes(graph,routes.pickup_hub_lon,routes.pickup_hub_lat)
    do=ox.distance.nearest_nodes(graph,routes.dropoff_hub_lon,routes.dropoff_hub_lat)
    records=[]
    for a,b in zip(pu,do):
        try:
            path=nx.shortest_path(graph,int(a),int(b),weight='travel_time')
            distance,duration=path_metrics(graph,path)
        except (nx.NetworkXNoPath,nx.NodeNotFound):path=[];distance=duration=float('nan')
        records.append({'pickup_road_node':int(a),'dropoff_road_node':int(b),'road_path_nodes':json.dumps(path),
                        'road_distance_m':distance,'road_travel_time_sec':duration})
    return pd.concat([routes.reset_index(drop=True),pd.DataFrame(records)],axis=1)

def plot_results(zones,od,pickup,dropoff,routes,out,graph=None):
    geo=zones.to_crs(4326)
    fig,axes=plt.subplots(1,2,figsize=(10,8))
    for ax,column,title in zip(axes,['PULocationID','DOLocationID'],['Pickup demand','Drop-off demand']):
        counts=od.groupby(column).demand.sum()
        layer=geo.merge(counts.rename('Trips'),left_on='LocationID',right_index=True,how='left')
        layer['Trips']=layer.Trips.fillna(0)
        layer.plot(column='Trips',cmap='Blues',legend=True,ax=ax,edgecolor='white',linewidth=.3)
        ax.set_title(title);ax.axis('off')
    fig.tight_layout();fig.savefig(out/'zone-demand.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,10))
    geo.plot(ax=ax,color='#f4f6f8',edgecolor='#c8d0db',linewidth=.5)
    for _,r in routes.iterrows():
        ax.plot([r.pickup_hub_lon,r.dropoff_hub_lon],[r.pickup_hub_lat,r.dropoff_hub_lat],color='#627da3',alpha=.30,
                linewidth=.5+3*r.demand/routes.demand.max())
    ax.scatter(pickup.lon,pickup.lat,label='Pickup hubs',color='#1a8b7b',s=42,zorder=4)
    ax.scatter(dropoff.lon,dropoff.lat,label='Drop-off hubs',color='#cf7b3c',s=42,marker='x',zorder=4)
    ax.set_title('Demand-weighted hub connections');ax.legend();ax.axis('off')
    fig.tight_layout();fig.savefig(out/'hub-connections.png',dpi=180);plt.close(fig)
    if graph is not None:
        valid=[json.loads(v) for v in routes.road_path_nodes if len(json.loads(v))>1]
        if valid:
            fig,ax=ox.plot_graph_routes(graph,valid,show=False,close=False,node_size=0,bgcolor='white',edge_color='#dfe4eb',route_alpha=.5)
            ax.set_title('Hub paths on the OSM drive network')
            fig.savefig(out/'hub-road-paths.png',dpi=180);plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--taxi-files',nargs='+',type=Path,default=[ROOT/'data/raw/yellow_tripdata_2026-03.parquet'])
    p.add_argument('--zone-shp',type=Path,default=ROOT/'data/raw/taxi_zones/taxi_zones.shp')
    p.add_argument('--zone-lookup',type=Path,default=ROOT/'data/raw/taxi_zone_lookup.csv')
    p.add_argument('--hubs',type=int,default=10);p.add_argument('--top-routes',type=int,default=50)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--graph-file',type=Path);p.add_argument('--road-network',action='store_true')
    p.add_argument('--output',type=Path,default=ROOT/'results/hub_analysis')
    args=p.parse_args()
    if args.top_routes<1:p.error('--top-routes must be positive.')
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    zones=load_zones(args.zone_shp,args.zone_lookup);od=load_od(args.taxi_files,set(zones.LocationID))
    if od.empty:raise ValueError('No Manhattan-to-Manhattan trips passed the filters.')
    pu,pickup=cluster_hubs(zones,od.groupby('PULocationID').demand.sum(),args.hubs,args.seed,'pickup')
    do,dropoff=cluster_hubs(zones,od.groupby('DOLocationID').demand.sum(),args.hubs,args.seed,'dropoff')
    mapped=od.merge(pu.rename(columns={'LocationID':'PULocationID','hub_id':'pickup_hub'}),on='PULocationID',validate='many_to_one')
    mapped=mapped.merge(do.rename(columns={'LocationID':'DOLocationID','hub_id':'dropoff_hub'}),on='DOLocationID',validate='many_to_one')
    hubs=mapped.groupby(['pickup_hub','dropoff_hub'],as_index=False).demand.sum().sort_values('demand',ascending=False)
    assert int(hubs.demand.sum())==int(od.demand.sum())
    routes=hubs.head(args.top_routes).merge(pickup.rename(columns={'hub_id':'pickup_hub','lon':'pickup_hub_lon','lat':'pickup_hub_lat'}).drop(columns='type'),on='pickup_hub')
    routes=routes.merge(dropoff.rename(columns={'hub_id':'dropoff_hub','lon':'dropoff_hub_lon','lat':'dropoff_hub_lat'}).drop(columns='type'),on='dropoff_hub')
    graph=None
    if args.graph_file:graph=ox.load_graphml(args.graph_file)
    elif args.road_network:
        graph=ox.graph_from_place('Manhattan, New York City, New York, USA',network_type='drive',simplify=True)
        graph=ox.routing.add_edge_speeds(graph,fallback=30);graph=ox.routing.add_edge_travel_times(graph)
        ox.save_graphml(graph,out/'road-network.graphml')
    if graph is not None:routes=add_road_paths(graph,routes)
    for name,frame in [('zone_od',od),('pickup_hubs',pickup),('dropoff_hubs',dropoff),('hub_od_matrix',hubs),('route_candidates',routes)]:frame.to_csv(out/f'{name}.csv',index=False)
    metadata={'version':'projected-weighted-hubs-v1','trips':int(od.demand.sum()),'pickup_hubs':len(pickup),'dropoff_hubs':len(dropoff),
              'top_route_share':float(routes.demand.sum()/hubs.demand.sum()),'seed':args.seed,'clustering_crs':'EPSG:2263',
              'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'inputs':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in args.taxi_files},
              'note':'Zone-centroid demand proxies; projected weighted KMeans. Not a rerun of the archived geographic-coordinate clustering.'}
    (out/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
    plot_results(zones,od,pickup,dropoff,routes,out,graph)
    print(json.dumps(metadata,indent=2))

if __name__=='__main__':main()
