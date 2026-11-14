import heapq
import math
from gare_au_poi.graph import RailwayGraph
from gare_au_poi.traversal import reconstruct_path

# Max TGV commercial speed in km/h (used to keep heuristic admissible: never overestimates)
MAX_TRAIN_SPEED_KMH = 320.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two (lat, lon) points."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def heuristic_minutes(graph: RailwayGraph, current_id: str, goal_id: str) -> float:
    """Admissible lower-bound travel time in minutes from current_id to goal_id."""
    s1 = graph.stations[current_id]
    s2 = graph.stations[goal_id]
    dist_km = haversine_km(s1.lat, s1.lon, s2.lat, s2.lon)
    return (dist_km / MAX_TRAIN_SPEED_KMH) * 60.0


def dijkstra_with_stats(
    graph: RailwayGraph, start_id: str, goal_id: str
) -> tuple[list[str], float, int] | None:
    """Dijkstra's algorithm returning (path, total_minutes, nodes_popped)."""
    pq: list[tuple[float, str]] = [(0.0, start_id)]
    best_cost: dict[str, float] = {start_id: 0.0}
    came_from: dict[str, str | None] = {start_id: None}
    nodes_expanded = 0

    while pq:
        g_cost, current_id = heapq.heappop(pq)
        if g_cost > best_cost.get(current_id, float("inf")):
            continue

        nodes_expanded += 1
        if current_id == goal_id:
            return reconstruct_path(came_from, goal_id), g_cost, nodes_expanded

        for neighbor_id, weight in graph.get_neighbors(current_id).items():
            new_g = g_cost + weight
            if new_g < best_cost.get(neighbor_id, float("inf")):
                best_cost[neighbor_id] = new_g
                came_from[neighbor_id] = current_id
                heapq.heappush(pq, (new_g, neighbor_id))

    return None


def astar_with_stats(
    graph: RailwayGraph, start_id: str, goal_id: str
) -> tuple[list[str], float, int] | None:
    """A* Search using Haversine heuristic, returning (path, total_minutes, nodes_popped)."""
    h_start = heuristic_minutes(graph, start_id, goal_id)
    # Heap stores (f_score = g + h, g_score, current_id)
    pq: list[tuple[float, float, str]] = [(h_start, 0.0, start_id)]
    best_g: dict[str, float] = {start_id: 0.0}
    came_from: dict[str, str | None] = {start_id: None}
    nodes_expanded = 0

    while pq:
        f_cost, g_cost, current_id = heapq.heappop(pq)
        if g_cost > best_g.get(current_id, float("inf")):
            continue

        nodes_expanded += 1
        if current_id == goal_id:
            return reconstruct_path(came_from, goal_id), g_cost, nodes_expanded

        for neighbor_id, weight in graph.get_neighbors(current_id).items():
            new_g = g_cost + weight
            if new_g < best_g.get(neighbor_id, float("inf")):
                best_g[neighbor_id] = new_g
                came_from[neighbor_id] = current_id
                f_score = new_g + heuristic_minutes(graph, neighbor_id, goal_id)
                heapq.heappush(pq, (f_score, new_g, neighbor_id))

    return None


if __name__ == "__main__":
    g = RailwayGraph.from_gtfs("DATA")

    pairs = [
        ("Bordeaux Saint-Jean", "Marseille Saint-Charles"),
        ("Bordeaux Saint-Jean", "Strasbourg"),
        ("Bègles", "Nice-Ville"),
    ]

    for origin_q, dest_q in pairs:
        start = g.find_stations_by_name(origin_q)[0]
        goal = g.find_stations_by_name(dest_q)[0]

        dij_path, dij_time, dij_nodes = dijkstra_with_stats(g, start.station_id, goal.station_id)
        ast_path, ast_time, ast_nodes = astar_with_stats(g, start.station_id, goal.station_id)
        reduction = (1 - ast_nodes / dij_nodes) * 100

        print(f"=== {start.name} -> {goal.name} ===")
        print(f"  Dijkstra: {dij_time:6.1f} min | Nodes explored: {dij_nodes}")
        print(f"  A* Search:{ast_time:6.1f} min | Nodes explored: {ast_nodes} ({reduction:.1f}% fewer nodes)\n")