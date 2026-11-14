import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


def parse_gtfs_time_to_seconds(time_str: str) -> int:
    """Convert GTFS HH:MM:SS string (including hours >= 24) into total seconds."""
    hours, minutes, seconds = map(int, time_str.strip().split(":"))
    return hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    lat: float
    lon: float


class RailwayGraph:
    """Weighted directed graph representing the SNCF railway network."""

    def __init__(self) -> None:
        self.stations: dict[str, Station] = {}
        # adjacency[u][v] = minimum travel duration in minutes
        self.adjacency: dict[str, dict[str, float]] = defaultdict(dict)

    @classmethod
    def from_gtfs(cls, data_folder: str | Path = "DATA") -> "RailwayGraph":
        graph = cls()
        data_path = Path(data_folder)

        stops_file = next(data_path.rglob("stops.txt"))
        stop_times_file = next(data_path.rglob("stop_times.txt"))

        point_to_station: dict[str, str] = {}

        # 1. Load Station Areas (vertices) and StopPoint -> StationArea mapping
        with open(stops_file, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                stop_id = row["stop_id"]
                if row["location_type"] == "1":
                    graph.stations[stop_id] = Station(
                        station_id=stop_id,
                        name=row["stop_name"],
                        lat=float(row["stop_lat"]),
                        lon=float(row["stop_lon"]),
                    )
                elif row["location_type"] == "0":
                    parent_id = row["parent_station"]
                    point_to_station[stop_id] = parent_id if parent_id else stop_id

        # 2. Stream stop_times.txt to populate directed weighted edges
        prev_trip_id: str | None = None
        prev_station_id: str | None = None
        prev_dep_sec: int = 0

        with open(stop_times_file, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                trip_id = row["trip_id"]
                station_id = point_to_station.get(row["stop_id"], row["stop_id"])

                arr_sec = parse_gtfs_time_to_seconds(row["arrival_time"])
                dep_sec = parse_gtfs_time_to_seconds(row["departure_time"])

                if trip_id == prev_trip_id and prev_station_id is not None:
                    if station_id != prev_station_id:
                        duration_min = (arr_sec - prev_dep_sec) / 60.0
                        if duration_min >= 0:
                            current_best = graph.adjacency[prev_station_id].get(station_id)
                            if current_best is None or duration_min < current_best:
                                graph.adjacency[prev_station_id][station_id] = duration_min

                prev_trip_id = trip_id
                prev_station_id = station_id
                prev_dep_sec = dep_sec

        return graph

    def find_stations_by_name(self, query: str) -> list[Station]:
        """Case-insensitive substring search for station areas."""
        q = query.lower()
        return [s for s in self.stations.values() if q in s.name.lower()]

    def get_neighbors(self, station_id: str) -> dict[str, float]:
        """Return {neighbor_station_id: min_duration_minutes}."""
        return self.adjacency.get(station_id, {})


if __name__ == "__main__":
    g = RailwayGraph.from_gtfs("DATA")
    print(f"Loaded {len(g.stations)} stations and {sum(len(v) for v in g.adjacency.values())} directed edges.")

    matches = g.find_stations_by_name("Bordeaux")
    print("\nMatches for 'Bordeaux':")
    for s in matches:
        print(f"  {s.station_id} -> {s.name} ({s.lat}, {s.lon})")

    if matches:
        bordeaux_st_jean = next((s for s in matches if "Saint-Jean" in s.name), matches[0])
        neighbors = g.get_neighbors(bordeaux_st_jean.station_id)
        print(f"\nDirect outgoing connections from {bordeaux_st_jean.name} ({len(neighbors)} neighbors):")
        for n_id, weight in sorted(neighbors.items(), key=lambda x: x[1])[:10]:
            n_name = g.stations[n_id].name if n_id in g.stations else n_id
            print(f"  -> {n_name:<30} | {weight:.1f} min")