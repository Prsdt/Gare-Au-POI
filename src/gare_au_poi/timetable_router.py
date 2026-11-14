import csv
import heapq
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from gare_au_poi.graph import Station, parse_gtfs_time_to_seconds

MIN_TRANSFER_SECONDS = 10 * 60  # 10 minutes minimum connection when changing trains


def format_seconds_to_hhmm(total_seconds: int) -> str:
    """Format seconds since midnight back into HH:MM (handling >= 24h)."""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


@dataclass(frozen=True)
class TimetableEdge:
    to_station_id: str
    dep_sec: int
    arr_sec: int
    trip_id: str
    route_name: str


class TimeDependentRailway:
    """Schedule-aware railway graph for a specific calendar date."""

    def __init__(self, target_date: str) -> None:
        self.target_date = target_date
        self.stations: dict[str, Station] = {}
        # departures[station_id] = list of TimetableEdge sorted by dep_sec
        self.departures: dict[str, list[TimetableEdge]] = defaultdict(list)

    @classmethod
    def for_date(cls, target_date: str, data_folder: str | Path = "DATA") -> "TimeDependentRailway":
        network = cls(target_date)
        data_path = Path(data_folder)

        # 1. Find all service_ids running on target_date
        active_services: set[str] = set()
        with open(next(data_path.rglob("calendar_dates.txt")), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row["date"] == target_date and row["exception_type"] == "1":
                    active_services.add(row["service_id"])

        # 2. Load route names
        route_names: dict[str, str] = {}
        with open(next(data_path.rglob("routes.txt")), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                short = row.get("route_short_name", "").strip()
                long_n = row.get("route_long_name", "").strip()
                route_names[row["route_id"]] = f"{short} ({long_n})".strip()

        # 3. Filter trips active on target_date
        active_trips: dict[str, str] = {}  # trip_id -> route_name
        with open(next(data_path.rglob("trips.txt")), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row["service_id"] in active_services:
                    active_trips[row["trip_id"]] = route_names.get(row["route_id"], row["route_id"])

        # 4. Load stations and StopPoint -> StationArea mapping
        point_to_station: dict[str, str] = {}
        with open(next(data_path.rglob("stops.txt")), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                stop_id = row["stop_id"]
                if row["location_type"] == "1":
                    network.stations[stop_id] = Station(
                        station_id=stop_id,
                        name=row["stop_name"],
                        lat=float(row["stop_lat"]),
                        lon=float(row["stop_lon"]),
                    )
                elif row["location_type"] == "0":
                    parent = row["parent_station"]
                    point_to_station[stop_id] = parent if parent else stop_id

        # 5. Stream stop_times.txt and keep only segments belonging to active_trips
        prev_trip_id: str | None = None
        prev_station_id: str | None = None
        prev_dep_sec: int = 0

        with open(next(data_path.rglob("stop_times.txt")), "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                trip_id = row["trip_id"]
                if trip_id not in active_trips:
                    prev_trip_id = None
                    continue

                station_id = point_to_station.get(row["stop_id"], row["stop_id"])
                arr_sec = parse_gtfs_time_to_seconds(row["arrival_time"])
                dep_sec = parse_gtfs_time_to_seconds(row["departure_time"])

                if trip_id == prev_trip_id and prev_station_id is not None and station_id != prev_station_id:
                    network.departures[prev_station_id].append(
                        TimetableEdge(
                            to_station_id=station_id,
                            dep_sec=prev_dep_sec,
                            arr_sec=arr_sec,
                            trip_id=trip_id,
                            route_name=active_trips[trip_id],
                        )
                    )

                prev_trip_id = trip_id
                prev_station_id = station_id
                prev_dep_sec = dep_sec

        # Sort outgoing departures chronologically at each station
        for st_id in network.departures:
            network.departures[st_id].sort(key=lambda e: e.dep_sec)

        return network

    def find_earliest_arrival(
        self, start_id: str, goal_id: str, earliest_dep_str: str
    ) -> list[tuple[str, TimetableEdge]] | None:
        """
        Time-Dependent Dijkstra: finds the itinerary arriving earliest at goal_id
        when departing start_id at or after earliest_dep_str (HH:MM:SS).
        """
        start_sec = parse_gtfs_time_to_seconds(earliest_dep_str)

        # Priority queue: (current_time_sec, current_station_id, current_trip_id)
        pq: list[tuple[int, str, str | None]] = [(start_sec, start_id, None)]
        best_arrival: dict[str, int] = {start_id: start_sec}
        came_from: dict[str, tuple[str, TimetableEdge]] = {}

        while pq:
            curr_time, curr_station, curr_trip = heapq.heappop(pq)

            if curr_time > best_arrival.get(curr_station, float("inf")):
                continue

            if curr_station == goal_id:
                # Reconstruct step-by-step itinerary
                legs: list[tuple[str, TimetableEdge]] = []
                node = goal_id
                while node in came_from:
                    prev_node, edge = came_from[node]
                    legs.append((prev_node, edge))
                    node = prev_node
                legs.reverse()
                return legs

            for edge in self.departures.get(curr_station, []):
                # Same train = 0s transfer; changing trains = 10 min transfer buffer
                required_dep = curr_time if edge.trip_id == curr_trip else (
                    curr_time if curr_trip is None else curr_time + MIN_TRANSFER_SECONDS
                )
                if edge.dep_sec < required_dep:
                    continue

                if edge.arr_sec < best_arrival.get(edge.to_station_id, float("inf")):
                    best_arrival[edge.to_station_id] = edge.arr_sec
                    came_from[edge.to_station_id] = (curr_station, edge)
                    heapq.heappush(pq, (edge.arr_sec, edge.to_station_id, edge.trip_id))

        return None


if __name__ == "__main__":
    DATE = "20261221"  # Monday, Dec 21, 2026
    DEPARTURE = "08:00:00"

    print(f"Building schedule graph for {DATE}...")
    td_graph = TimeDependentRailway.for_date(DATE, "DATA")

    bordeaux = next(s for s in td_graph.stations.values() if s.name == "Bordeaux Saint-Jean")
    marseille = next(s for s in td_graph.stations.values() if s.name == "Marseille Saint-Charles")

    itinerary = td_graph.find_earliest_arrival(bordeaux.station_id, marseille.station_id, DEPARTURE)

    print(f"\nEarliest Arrival Itinerary: {bordeaux.name} -> {marseille.name}")
    print(f"Date: {DATE} | Requested Departure >= {DEPARTURE}\n")

    if itinerary:
        first_dep = itinerary[0][1].dep_sec
        last_arr = itinerary[-1][1].arr_sec
        total_min = (last_arr - first_dep) / 60.0
        print(f"Departure: {format_seconds_to_hhmm(first_dep)} | Arrival: {format_seconds_to_hhmm(last_arr)} | Total Door-to-Door: {total_min:.0f} min\n")

        for from_id, edge in itinerary:
            from_name = td_graph.stations[from_id].name
            to_name = td_graph.stations[edge.to_station_id].name
            print(
                f"  {format_seconds_to_hhmm(edge.dep_sec)} {from_name:<28} -> "
                f"{format_seconds_to_hhmm(edge.arr_sec)} {to_name:<28} | [{edge.route_name}]"
            )
    else:
        print("No valid itinerary found.")