import heapq
from app.engine.graph import RailwayGraph
from app.engine.traversal import bfs_path, calculate_path_duration, reconstruct_path


def dijkstra_shortest_path(
    graph: RailwayGraph, start_id: str, goal_id: str
) -> tuple[list[str], float] | None:
    """
    Find the minimum-duration path between start_id and goal_id using Dijkstra's algorithm.
    Returns (path_of_station_ids, total_duration_minutes) or None if unreachable.
    """
    if start_id not in graph.stations or goal_id not in graph.stations:
        return None

    # Min-heap storing (cumulative_minutes, current_station_id)
    priority_queue: list[tuple[float, str]] = [(0.0, start_id)]
    best_cost: dict[str, float] = {start_id: 0.0}
    came_from: dict[str, str | None] = {start_id: None}

    while priority_queue:
        current_cost, current_id = heapq.heappop(priority_queue)

        # Skip stale heap entries if we already found a faster way to current_id
        if current_cost > best_cost.get(current_id, float("inf")):
            continue

        if current_id == goal_id:
            return reconstruct_path(came_from, goal_id), current_cost

        for neighbor_id, travel_min in graph.get_neighbors(current_id).items():
            new_cost = current_cost + travel_min
            if new_cost < best_cost.get(neighbor_id, float("inf")):
                best_cost[neighbor_id] = new_cost
                came_from[neighbor_id] = current_id
                heapq.heappush(priority_queue, (new_cost, neighbor_id))

    return None


def compare_algorithms(graph: RailwayGraph, origin_query: str, dest_query: str) -> None:
    start = graph.find_stations_by_name(origin_query)[0]
    goal = graph.find_stations_by_name(dest_query)[0]

    print(f"============================================================")
    print(f"QUERY: {start.name}  --->  {goal.name}")
    print(f"============================================================")

    bfs_res = bfs_path(graph, start.station_id, goal.station_id)
    if bfs_res:
        bfs_time = calculate_path_duration(graph, bfs_res)
        print(f"[BFS - Fewest Stops]  {len(bfs_res) - 1} stops | {bfs_time:.1f} min")
        print("   " + " -> ".join(graph.stations[s].name for s in bfs_res))

    dijkstra_res = dijkstra_shortest_path(graph, start.station_id, goal.station_id)
    if dijkstra_res:
        dij_path, dij_time = dijkstra_res
        print(f"\n[Dijkstra - Fastest]  {len(dij_path) - 1} stops | {dij_time:.1f} min")
        print("   " + " -> ".join(graph.stations[s].name for s in dij_path))
    print()


if __name__ == "__main__":
    g = RailwayGraph.from_gtfs("DATA")

    compare_algorithms(g, "Bordeaux Saint-Jean", "Lyon Part Dieu")
    compare_algorithms(g, "Bordeaux Saint-Jean", "Marseille Saint-Charles")
    compare_algorithms(g, "Bègles", "Paris Montparnasse")