from collections import deque
from app.engine.graph import RailwayGraph


def reconstruct_path(came_from: dict[str, str | None], goal_id: str) -> list[str]:
    """Trace parent pointers backward from goal_id to start_id."""
    path: list[str] = []
    current: str | None = goal_id
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def bfs_path(graph: RailwayGraph, start_id: str, goal_id: str) -> list[str] | None:
    """Find a path with the fewest stops using Breadth-First Search (Queue)."""
    if start_id not in graph.stations or goal_id not in graph.stations:
        return None

    queue: deque[str] = deque([start_id])
    came_from: dict[str, str | None] = {start_id: None}

    while queue:
        current = queue.popleft()  # FIFO: pop from front
        if current == goal_id:
            return reconstruct_path(came_from, goal_id)

        for neighbor in graph.get_neighbors(current):
            if neighbor not in came_from:
                came_from[neighbor] = current
                queue.append(neighbor)

    return None


def dfs_path(graph: RailwayGraph, start_id: str, goal_id: str) -> list[str] | None:
    """Find any valid path using iterative Depth-First Search (Stack)."""
    if start_id not in graph.stations or goal_id not in graph.stations:
        return None

    stack: list[str] = [start_id]
    came_from: dict[str, str | None] = {start_id: None}

    while stack:
        current = stack.pop()  # LIFO: pop from top
        if current == goal_id:
            return reconstruct_path(came_from, goal_id)

        for neighbor in graph.get_neighbors(current):
            if neighbor not in came_from:
                came_from[neighbor] = current
                stack.append(neighbor)

    return None


def calculate_path_duration(graph: RailwayGraph, path: list[str]) -> float:
    """Sum edge weights (in minutes) along a sequence of station IDs."""
    total_min = 0.0
    for u, v in zip(path, path[1:]):
        total_min += graph.adjacency[u][v]
    return total_min


if __name__ == "__main__":
    g = RailwayGraph.from_gtfs("DATA")

    # Bordeaux Saint-Jean -> Lyon Part Dieu
    start_station = g.find_stations_by_name("Bordeaux Saint-Jean")[0]
    goal_station = g.find_stations_by_name("Lyon Part Dieu")[0]

    print(f"Origin:      {start_station.name} ({start_station.station_id})")
    print(f"Destination: {goal_station.name} ({goal_station.station_id})\n")

    path_bfs = bfs_path(g, start_station.station_id, goal_station.station_id)
    if path_bfs:
        dur_bfs = calculate_path_duration(g, path_bfs)
        print(f"========== BFS RESULT (Fewest Stops) ==========")
        print(f"Stops traversed: {len(path_bfs) - 1} segments | Total travel time: {dur_bfs:.1f} min")
        print("Route: " + " -> ".join(g.stations[s].name for s in path_bfs))

    path_dfs = dfs_path(g, start_station.station_id, goal_station.station_id)
    if path_dfs:
        dur_dfs = calculate_path_duration(g, path_dfs)
        print(f"\n========== DFS RESULT (First Deep Branch) ==========")
        print(f"Stops traversed: {len(path_dfs) - 1} segments | Total travel time: {dur_dfs:.1f} min")
        print(f"First 5 stops: {' -> '.join(g.stations[s].name for s in path_dfs[:5])} ...")
        print(f"Last 5 stops:  ... {' -> '.join(g.stations[s].name for s in path_dfs[-5:])}")