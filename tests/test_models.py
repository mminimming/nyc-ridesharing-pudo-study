"""Small offline regression tests for assignment and routing correctness."""
from pathlib import Path
import sys
import unittest
import networkx as nx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dynamic_assignment import (Request, Vehicle, GroupVehicleEdge, SimParams,
                               TravelTimeCache, solve_assignment_ilp, run_simulation)
from hub_analysis import path_metrics

class ModelTests(unittest.TestCase):
    def test_overlapping_groups_cannot_serve_request_twice(self):
        requests = [Request(i, 0, 0, 2, 1, 20) for i in (1, 2, 3)]
        vehicles = [Vehicle(i, 0) for i in range(3)]
        # An at-least-once formulation selects both cheap pairs and duplicates ID 2.
        edges = [GroupVehicleEdge(0, (1,2), 0, 1, 0, [], {}),
                 GroupVehicleEdge(1, (2,3), 1, 1, 0, [], {}),
                 GroupVehicleEdge(2, (3,), 2, 5, 0, [], {}),
                 GroupVehicleEdge(3, (1,), 2, 5, 0, [], {})]
        chosen, rejected = solve_assignment_ilp(requests, vehicles, edges, SimParams())
        ids = [rid for edge in chosen for rid in edge.group]
        self.assertEqual(sorted(ids), [1,2,3])
        self.assertEqual(rejected, [])
        self.assertAlmostEqual(sum(e.cost for e in chosen), 6)

    def test_distance_matches_fastest_parallel_edge(self):
        graph = nx.MultiDiGraph()
        graph.add_edge(0,1,length=10,travel_time=20)
        graph.add_edge(0,1,length=100,travel_time=5)
        graph.add_edge(1,2,length=20,travel_time=2)
        self.assertEqual(path_metrics(graph, [0,1,2]), (120,7))

    def test_two_request_simulation_both_scenarios(self):
        graph = nx.MultiDiGraph()
        for a,b in [(0,1),(1,0),(1,2),(2,1)]:
            graph.add_edge(a,b,length=13.5,travel_time=10)
        requests = [Request(i,0,0,2,1,20) for i in (1,2)]
        params = SimParams(pudo_candidate_limit=2)
        for walking in (False, True):
            with self.subTest(walking=walking):
                frame = run_simulation(requests, [Vehicle(0,0,capacity=2)],
                                       TravelTimeCache(graph,1.35), params, walking)
                self.assertEqual(len(frame), 2)
                self.assertTrue(frame.rid.is_unique)
                self.assertTrue(frame.accepted.all())
                self.assertTrue((frame.wait <= params.omega_wait).all())
                self.assertTrue((frame.walk <= 2*params.omega_walk).all())
                self.assertTrue((frame.delay <= params.omega_delay).all())

if __name__ == "__main__":
    unittest.main()
