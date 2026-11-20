from dataclasses import dataclass
from app.engine.astar import haversine_km
from app.engine.graph import Station
from app.engine.timetable_router import (
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


@dataclass(frozen=True)
class MultimodalPlan:
    origin: Station
    dest_station: Station
    poi: PointOfInterest
    walk_km: float
    walk_sec: int
    legs: list[tuple[str, TimetableEdge]]
    poi_arrival_sec: int


def find_nearest_stations(
    stations: dict[str, Station], lat: float, lon: float, top_k: int = 3
) -> list[tuple[Station, float, int]]:
    """Find the top_k closest stations to (lat, lon)."""
    scored: list[tuple[Station, float, int]] = []
    for st in stations.values():
        dist_km = haversine_km(lat, lon, st.lat, st.lon)
        walk_sec = int(round((dist_km / WALKING_SPEED_KMH) * 3600))
        scored.append((st, dist_km, walk_sec))

    scored.sort(key=lambda item: item[1])
    return scored[:top_k]


def compute_trip_to_poi(
    network: TimeDependentRailway,
    origin_station_name: str,
    poi: PointOfInterest,
    departure_time_str: str,
) -> MultimodalPlan | None:
    """Compute the earliest-arrival multimodal itinerary from origin station to POI."""
    origin = next(
        (s for s in network.stations.values() if origin_station_name.lower() in s.name.lower()),
        None,
    )
    if origin is None:
        return None

    nearby_stations = find_nearest_stations(network.stations, poi.lat, poi.lon, top_k=3)

    best_total_arrival_sec: int | None = None
    best_plan: MultimodalPlan | None = None

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
            best_plan = MultimodalPlan(
                origin=origin,
                dest_station=dest_station,
                poi=poi,
                walk_km=dist_km,
                walk_sec=walk_sec,
                legs=legs,
                poi_arrival_sec=poi_arrival_sec,
            )

    return best_plan


def plan_trip_to_poi(
    network: TimeDependentRailway,
    origin_station_name: str,
    poi: PointOfInterest,
    departure_time_str: str,
) -> MultimodalPlan | None:
    plan = compute_trip_to_poi(network, origin_station_name, poi, departure_time_str)
    print("=================================================================")
    print(f"GARE-AU-POI PLANNER: {origin_station_name}  --->  {poi.name}")
    print(f"Date: {network.target_date} | Earliest Departure: {departure_time_str}")
    print("=================================================================")

    if plan is None:
        print("No multimodal route found.")
        return None

    first_dep_sec = plan.legs[0][1].dep_sec
    total_minutes = (plan.poi_arrival_sec - first_dep_sec) / 60.0

    print(
        f"Board at:  {format_seconds_to_hhmm(first_dep_sec)} ({plan.origin.name})\n"
        f"Reach POI: {format_seconds_to_hhmm(plan.poi_arrival_sec)} ({plan.poi.name}) "
        f"| Total Time: {total_minutes:.0f} min\n"
    )

    print("1. Rail Journey:")
    current_trip: str | None = None
    for idx, (from_id, edge) in enumerate(plan.legs):
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
        f"   Walk {plan.walk_km:.2f} km (~{plan.walk_sec // 60} min) "
        f"from {plan.dest_station.name} to {plan.poi.name}"
    )
    print("=================================================================\n")
    return plan