"""Validate preserved file hashes and request-level summary consistency."""
from pathlib import Path
import csv
import hashlib
import json
import math
ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "results/archived/provenance.json").read_text())
for path, entry in manifest["files"].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == entry["sha256"], path
folder = ROOT / "results/archived/dynamic_assignment"
with (folder/"nyc_pudo_gv_results_summary.csv").open() as f:
    summary = list(csv.DictReader(f))
for scenario, suffix in zip(summary, ["door","pudo"]):
    with (folder/f"nyc_pudo_gv_results_{suffix}.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == int(scenario["requests"])
    assert len({r["rid"] for r in rows}) == len(rows)
    accepted = [r for r in rows if r["accepted"].lower() == "true"]
    assert len(accepted) == int(scenario["accepted"])
    for raw, agg in [("wait","avg_wait_min"),("walk","avg_walk_min"),("delay","avg_delay_min")]:
        value = sum(float(r[raw]) for r in accepted)/len(accepted)/60
        assert math.isclose(value, float(scenario[agg]), abs_tol=1e-9), agg
print("Archive hashes and request-level summary checks passed.")
