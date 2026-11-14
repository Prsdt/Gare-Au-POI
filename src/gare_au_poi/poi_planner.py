from dataclasses import dataclass
from gare_au_poi.astar import haversine_km
from gare_au_poi.graph import Station, parse_gtfs_time_to_seconds
from gare_au_poi.timetable_router import (
    TimeDependentRailway,
    TimetableEdge,
    format_seconds_to_hhmm,
)

WALKING_SPEED_KMH = 5.0


@dataclass(frozen=True)
class PointOfInterest:
    name: str
    lat: float
    lon: float


def find_nearest_stations(
    stations: dict[str, Station], lat: float, lon: float, top_k: int = 3
) -> list[tuple[Station, float, int]]:
    """
    Find the top_k closest stations to (lat, lon).
    Returns a list of (Station, distance_km, walking_seconds).
    """
    scored: list[tuple[Station, float, int]] = []
    for st in stations.values():
        dist_km = haversine_km(lat, lon, st.lat, st.lon)
        walk_sec = int(round((dist_km / WALKING_SPEED_KMH) * 3600))
        scored.append((st, dist_km, walk_sec))

    scored.sort(key=lambda item: item[1])
    return scored[:top_k]


def plan_trip_to_poi(
    network: TimeDependentRailway,
    origin_station_name: str,
    poi: PointOfInterest,
    departure_time_str: str,
) -> None:
    origin = next(
        (s for s in network.stations.values() if origin_station_name.lower() in s.name.lower()),
        None,
    )
    if origin is None:
        print(f"Origin station '{origin_station_name}' not found.")
        return

    nearby_stations = find_nearest_stations(network.stations, poi.lat, poi.lon, top_k=3)

    best_total_arrival_sec: int | None = None
    best_plan: tuple[Station, float, int, list[tuple[str, TimetableEdge]]] | None = None

    # Evaluate routing to each of the 3 nearest stations + walking to POI
    for dest_station, dist_km, walk_sec in nearby_stations:
        legs = network.find_earliest_arrival(
            origin.station_id, dest_station.station_id, departure_time_str
        )
        if not legs:
            continue

        train_arrival_sec = legs[-1][1].arr_sec
        poi_arrival_sec = train_arrival_sec + walk_sec

        if best_total_arrival_sec is None or poi_arrival_sec < best_total_arrival_sec:
            best_total_arrival_sec = poi_arrival_sec
            best_plan = (dest_station, dist_km, walk_sec, legs)

    print("=================================================================")
    print(f"GARE-AU-POI PLANNER: {origin.name}  --->  {poi.name}")
    print(f"Date: {network.target_date} | Earliest Departure: {departure_time_str}")
    print("=================================================================")

    if best_plan is None or best_total_arrival_sec is None:
        print("No multimodal route found.")
        return

    dest_station, dist_km, walk_sec, legs = best_plan
    first_dep_sec = legs[0][1].dep_sec
    total_minutes = (best_total_arrival_sec - first_dep_sec) / 60.0

    print(
        f"Board at:  {format_seconds_to_hhmm(first_dep_sec)} ({origin.name})\n"
        f"Reach POI: {format_seconds_to_hhmm(best_total_arrival_sec)} ({poi.name}) "
        f"| Total Time: {total_minutes:.0f} min\n"
    )

    # Summarize contiguous train segments (grouping consecutive stops on the same trip)
    print("1. Rail Journey:")
    current_trip: str | None = None
    for idx, (from_id, edge) in enumerate(legs):
        from_name = network.stations[from_id].name
        to_name = network.stations[edge.to_station_id].name
        if edge.trip_id != current_trip:
            if idx > 0:
                print("   --- [Transfer: min 10 min connection] ---")
            current_trip = edge.trip_id
        print(
            f"   {format_seconds_to_hhmm(edge.dep_sec)} {from_name:<26} -> "
            f"{format_seconds_to_hhmm(edge.arr_sec)} {to_name:<26} | {edge.route_name}"
        )

    print(
        f"\n2. Last-Mile Walk:\n"
        f"   Walk {dist_km:.2f} km (~{walk_sec // 60} min) from {dest_station.name} to {poi.name}"
    )
    print("=================================================================\n")


if __name__ == "__main__":
    DATE = "20261221"
    td_network = TimeDependentRailway.for_date(DATE, "DATA")

    # Example 1: Bègles -> Vieux-Port de Marseille (requires TER -> Intercités transfer at Bordeaux!)
    vieux_port = PointOfInterest("Vieux-Port de Marseille", lat=43.2951, lon=5.3744)
    plan_trip_to_poi(td_network, "Bègles", vieux_port, "07:30:00")

    # Example 2: Bordeaux Saint-Jean -> Tour Eiffel (Paris)
    tour_eiffel = PointOfInterest("Tour Eiffel (Paris)", lat=48.8584, lon=2.2945)
    plan_trip_to_poi(td_network, "Bordeaux Saint-Jean", tour_eiffel, "08:00:00")