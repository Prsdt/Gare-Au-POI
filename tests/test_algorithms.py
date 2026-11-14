import unittest
from gare_au_poi.astar import astar_with_stats, dijkstra_with_stats, haversine_km
from gare_au_poi.graph import RailwayGraph, Station, parse_gtfs_time_to_seconds
from gare_au_poi.traversal import bfs_path, dfs_path


class TestGareAuPOI(unittest.TestCase):
    def setUp(self) -> None:
        # Build a small synthetic railway graph for fast unit testing
        self.g = RailwayGraph()
        self.g.stations = {
            "A": Station("A", "Gare A", 44.8258, -0.5567),
            "B": Station("B", "Gare B", 44.8500, -0.5000),
            "C": Station("C", "Gare C", 44.9000, -0.4500),
            "D": Station("D", "Gare D", 45.7606, 4.8594),
        }
        # Direct slow route: A -> D (2 hops, 300 min)
        # Multi-stop high-speed route: A -> B -> C -> D (3 hops, 180 min)
        self.g.adjacency["A"]["D"] = 300.0
        self.g.adjacency["A"]["B"] = 50.0
        self.g.adjacency["B"]["C"] = 60.0
        self.g.adjacency["C"]["D"] = 70.0

    def test_gtfs_post_midnight_time_parsing(self) -> None:
        self.assertEqual(parse_gtfs_time_to_seconds("08:30:00"), 8 * 3600 + 30 * 60)
        self.assertEqual(parse_gtfs_time_to_seconds("25:15:30"), 25 * 3600 + 15 * 60 + 30)

    def test_bfs_vs_dijkstra_and_astar(self) -> None:
        # BFS chooses fewest stops (A -> D)
        self.assertEqual(bfs_path(self.g, "A", "D"), ["A", "D"])
        self.assertIsNotNone(dfs_path(self.g, "A", "D"))

        # Dijkstra & A* both choose fastest travel duration (A -> B -> C -> D = 180 min)
        dij_path, dij_cost, _ = dijkstra_with_stats(self.g, "A", "D")
        ast_path, ast_cost, _ = astar_with_stats(self.g, "A", "D")
        self.assertEqual(dij_path, ["A", "B", "C", "D"])
        self.assertEqual(ast_path, ["A", "B", "C", "D"])
        self.assertAlmostEqual(dij_cost, 180.0)
        self.assertAlmostEqual(ast_cost, 180.0)

    def test_haversine_distance(self) -> None:
        dist = haversine_km(44.8258, -0.5567, 44.8258, -0.5567)
        self.assertAlmostEqual(dist, 0.0)


if __name__ == "__main__":
    unittest.main()