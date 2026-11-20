import csv
from collections import defaultdict
from pathlib import Path


def parse_gtfs_time_to_seconds(time_str: str) -> int:
    """Convert GTFS HH:MM:SS string (including hours >= 24) into total seconds."""
    hours, minutes, seconds = map(int, time_str.strip().split(":"))
    return hours * 3600 + minutes * 60 + seconds


def main() -> None:
    data_folder = Path("DATA")
    stops_file = next(data_folder.rglob("stops.txt"))
    stop_times_file = next(data_folder.rglob("stop_times.txt"))

    # 1. Load Station Areas and map Stop Points -> Parent Station Area
    station_names = {}
    point_to_station = {}

    with open(stops_file, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            stop_id = row["stop_id"]
            if row["location_type"] == "1":
                station_names[stop_id] = row["stop_name"]
            elif row["location_type"] == "0":
                parent_id = row["parent_station"]
                point_to_station[stop_id] = parent_id if parent_id else stop_id

    # 2. Stream stop_times.txt to build directed station-to-station edges
    # adjacency[u][v] stores a list of travel durations (in minutes)
    adjacency = defaultdict(lambda: defaultdict(list))
    skipped_self_loops = 0
    invalid_durations = 0

    prev_trip_id = None
    prev_station_id = None
    prev_dep_sec = None

    with open(stop_times_file, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            trip_id = row["trip_id"]
            stop_point_id = row["stop_id"]
            station_id = point_to_station.get(stop_point_id, stop_point_id)

            arr_sec = parse_gtfs_time_to_seconds(row["arrival_time"])
            dep_sec = parse_gtfs_time_to_seconds(row["departure_time"])

            if trip_id == prev_trip_id:
                if station_id == prev_station_id:
                    skipped_self_loops += 1
                else:
                    duration_min = (arr_sec - prev_dep_sec) / 60.0
                    if duration_min >= 0:
                        adjacency[prev_station_id][station_id].append(duration_min)
                    else:
                        invalid_durations += 1

            prev_trip_id = trip_id
            prev_station_id = station_id
            prev_dep_sec = dep_sec

    # 3. Compute Graph Topology Summary
    active_nodes = set(adjacency.keys())
    for u, neighbors in adjacency.items():
        active_nodes.update(neighbors.keys())

    total_directed_edges = sum(len(neighbors) for neighbors in adjacency.values())

    # Find the busiest rail segment (most scheduled trips between two consecutive stations)
    busiest_segment = None
    max_trips = 0
    for u, neighbors in adjacency.items():
        for v, durations in neighbors.items():
            if len(durations) > max_trips:
                max_trips = len(durations)
                busiest_segment = (u, v, min(durations), sum(durations) / len(durations))

    print("========== RAILWAY GRAPH SUMMARY ==========")
    print(f"Total Station Areas in stops.txt: {len(station_names)}")
    print(f"Connected Station Nodes in Graph: {len(active_nodes)}")
    print(f"Unique Directed Edges (u -> v):   {total_directed_edges}")
    print(f"Skipped self-loops:               {skipped_self_loops}")
    print(f"Negative/invalid durations:       {invalid_durations}")

    if busiest_segment:
        u, v, min_d, avg_d = busiest_segment
        u_name = station_names.get(u, u)
        v_name = station_names.get(v, v)
        print(f"\nBusiest Direct Rail Segment:")
        print(f"  {u_name} ({u}) -> {v_name} ({v})")
        print(f"  Scheduled trips: {max_trips} | Min time: {min_d:.1f} min | Avg time: {avg_d:.1f} min")
    print("===========================================")


if __name__ == "__main__":
    main()