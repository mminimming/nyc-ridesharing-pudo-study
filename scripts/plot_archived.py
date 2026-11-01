"""Regenerate the English comparison figure from preserved CSV output."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
summary = pd.read_csv(ROOT / "results/archived/dynamic_assignment/nyc_pudo_gv_results_summary.csv")
summary = summary.set_index("scenario").loc[["door_to_door_gv", "pudo_walking_gv"]]
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
                     "axes.spines.top":False, "axes.spines.right":False})
fig, axes = plt.subplots(1,4,figsize=(12,3.4))
metrics = [("avg_wait_min", "Waiting", "Minutes / accepted request"),
           ("avg_walk_min", "Walking", "Minutes / accepted request"),
           ("avg_delay_min", "Arrival delay", "Minutes / accepted request"),
           ("vht_hours", "Vehicle service time", "Total vehicle-hours")]
for ax,(column,title,unit) in zip(axes,metrics):
    vals = summary[column].to_numpy()
    bars = ax.bar([0,1],vals,color=["#54769b","#168878"],width=.6)
    ax.set_xticks([0,1],["Door-to-door","PUDO"])
    ax.set_title(title,fontweight="bold"); ax.set_ylabel(unit)
    ax.set_ylim(0,max(vals.max()*1.3,1))
    ax.bar_label(bars,fmt="%.2f",padding=4)
    ax.set_axisbelow(True);ax.grid(axis="y",alpha=.15)
fig.suptitle("Archived prototype output · 98 requests",fontweight="bold",y=.99)
fig.tight_layout(rect=(0,0,1,.93))
for suffix in ("png","svg"):
    fig.savefig(ROOT / f"figures/archived-assignment-comparison.{suffix}",dpi=200)
