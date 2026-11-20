import heapq
import os
from functools import lru_cache
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.emissions import CO2_G_PER_KM, compute_leg_metrics
from app.engine.graph import RailwayGraph, parse_gtfs_time_to_seconds
from app.engine.poi_planner import find_nearest_stations
from app.engine.timetable_router import (
    MIN_TRANSFER_SECONDS,
    TimeDependentRailway,
    TimetableEdge,
    format_seconds_to_hhmm,
)
from app.pois_catalog import CATALOG_POIS

DATA_DIR = Path(os.getenv("GTFS_DATA_DIR", Path(__file__).resolve().parents[2] / "DATA"))

app = FastAPI(title="Gare-Au-POI API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_static_graph() -> RailwayGraph:
    return RailwayGraph.from_gtfs(DATA_DIR)


@lru_cache(maxsize=8)
def get_timetable_network(target_date: str) -> TimeDependentRailway:
    return TimeDependentRailway.for_date(target_date, DATA_DIR)


class POIInput(BaseModel):
    name: str
    lat: float
    lon: float
    visit_duration_min: int = Field(default=60, ge=0, le=720)


class RouteRequest(BaseModel):
    origin_station_id: str | None = None
    origin_lat: float | None = None
    origin_lon: float | None = None
    origin_label: str = "Ma position"
    pois: list[POIInput] = Field(..., min_length=1)
    date: str = Field(default="20261221", pattern=r"^\d{8}$")
    departure_time: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    criterion: str = Field(default="fastest", pattern=r"^(fastest|fewest_transfers|lowest_co2)$")


def optimize_legs_by_criterion(
    network: TimeDependentRailway,
    start_id: str,
    goal_id: str,
    earliest_dep_sec: int,
    criterion: str,
) -> list[tuple[str, TimetableEdge]] | None:
    if start_id == goal_id:
        return []

    pq: list[tuple[float, int, str, str | None]] = [(0.0, earliest_dep_sec, start_id, None)]
    best_state: dict[tuple[str, str | None], tuple[float, int]] = {(start_id, None): (0.0, earliest_dep_sec)}
    came_from: dict[tuple[str, str | None], tuple[tuple[str, str | None], str, TimetableEdge]] = {}
    best_goal_key: tuple[str, str | None] | None = None

    while pq:
        primary_cost, curr_time, curr_st, curr_trip = heapq.heappop(pq)
        state_key = (curr_st, curr_trip)

        if (primary_cost, curr_time) > best_state.get(state_key, (float("inf"), 10**9)):
            continue

        if curr_st == goal_id:
            best_goal_key = state_key
            break

        for edge in network.departures.get(curr_st, []):
            is_transfer = (curr_trip is not None) and (edge.trip_id != curr_trip)
            req_dep = curr_time + (MIN_TRANSFER_SECONDS if is_transfer else 0)
            if edge.dep_sec < req_dep:
                continue

            if criterion == "fastest":
                new_primary = float(edge.arr_sec)
            elif criterion == "fewest_transfers":
                new_primary = primary_cost + (100000.0 if is_transfer else 0.0) + (edge.arr_sec - curr_time)
            else:
                metrics = compute_leg_metrics(network.stations, curr_st, edge)
                new_primary = primary_cost + metrics["co2_g"] + (edge.arr_sec - curr_time) * 0.01

            next_key = (edge.to_station_id, edge.trip_id)
            if (new_primary, edge.arr_sec) < best_state.get(next_key, (float("inf"), 10**9)):
                best_state[next_key] = (new_primary, edge.arr_sec)
                came_from[next_key] = (state_key, curr_st, edge)
                heapq.heappush(pq, (new_primary, edge.arr_sec, edge.to_station_id, edge.trip_id))

    if best_goal_key is None:
        return None

    legs: list[tuple[str, TimetableEdge]] = []
    cursor = best_goal_key
    while cursor in came_from:
        prev_key, from_st, edge = came_from[cursor]
        legs.append((from_st, edge))
        cursor = prev_key
    legs.reverse()
    return legs


@app.get("/api/health")
def health() -> dict:
    g = get_static_graph()
    return {"status": "ok", "stations_loaded": len(g.stations)}


@app.get("/api/stations")
def search_stations(q: str = Query(default="", min_length=0)) -> list[dict]:
    g = get_static_graph()
    matches = g.find_stations_by_name(q) if q else list(g.stations.values())
    matches.sort(key=lambda s: s.name)
    return [
        {"station_id": s.station_id, "name": s.name, "lat": s.lat, "lon": s.lon}
        for s in matches[:30]
    ]


@app.get("/api/pois")
def list_pois() -> list[dict]:
    return CATALOG_POIS


@app.post("/api/route")
def compute_multimodal_route(req: RouteRequest) -> dict:
    network = get_timetable_network(req.date)
    dep_str = req.departure_time if len(req.departure_time) == 8 else f"{req.departure_time}:00"
    base_dep_sec = parse_gtfs_time_to_seconds(dep_str)

    features: list[dict] = []
    total_distance_km = 0.0
    total_co2_g = 0.0
    total_transfers = 0
    initial_walk_info = None

    # Resolve starting point: either a station ID or user GPS coordinates
    if req.origin_station_id:
        if req.origin_station_id not in network.stations:
            raise HTTPException(status_code=404, detail="Gare de départ introuvable.")
        current_station = network.stations[req.origin_station_id]
        current_time_sec = base_dep_sec
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [current_station.lon, current_station.lat]},
            "properties": {"name": current_station.name, "role": "origin", "detail": f"Départ {dep_str[:5]}"},
        })
    elif req.origin_lat is not None and req.origin_lon is not None:
        nearest = find_nearest_stations(network.stations, req.origin_lat, req.origin_lon, top_k=1)
        if not nearest:
            raise HTTPException(status_code=404, detail="Aucune gare trouvée à proximité.")
        current_station, walk_km, walk_sec = nearest[0]
        current_time_sec = base_dep_sec + walk_sec
        total_distance_km += walk_km
        initial_walk_info = {
            "from": req.origin_label,
            "to_station": current_station.name,
            "walk_km": round(walk_km, 2),
            "walk_min": walk_sec // 60,
        }
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [req.origin_lon, req.origin_lat]},
            "properties": {"name": req.origin_label, "role": "origin", "detail": f"Position de départ ({dep_str[:5]})"},
        })
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[req.origin_lon, req.origin_lat], [current_station.lon, current_station.lat]]},
            "properties": {"mode": "walk", "from": req.origin_label, "to": current_station.name, "distance_km": round(walk_km, 2), "duration_min": walk_sec // 60},
        })
    else:
        raise HTTPException(status_code=400, detail="Veuillez indiquer une gare de départ ou une position GPS.")

    stages: list[dict] = []
    journey_start_sec: int | None = base_dep_sec if initial_walk_info else None

    for stage_idx, poi in enumerate(req.pois):
        candidates = find_nearest_stations(network.stations, poi.lat, poi.lon, top_k=3)
        best_choice = None

        for dest_st, walk_km, walk_sec in candidates:
            legs = optimize_legs_by_criterion(
                network, current_station.station_id, dest_st.station_id, current_time_sec, req.criterion
            )
            if legs is None:
                continue
            arr_at_poi = (legs[-1][1].arr_sec if legs else current_time_sec) + walk_sec
            if best_choice is None or arr_at_poi < best_choice[0]:
                best_choice = (arr_at_poi, dest_st, walk_km, walk_sec, legs)

        if best_choice is None:
            raise HTTPException(
                status_code=404,
                detail=f"Aucun horaire ferroviaire trouvé entre {current_station.name} et {poi.name} le {req.date}.",
            )

        arr_at_poi, dest_st, walk_km, walk_sec, legs = best_choice
        stage_legs_out = []
        prev_trip: str | None = None

        for leg_i, (from_id, edge) in enumerate(legs):
            if journey_start_sec is None:
                journey_start_sec = edge.dep_sec
            if prev_trip is not None and edge.trip_id != prev_trip:
                total_transfers += 1
            prev_trip = edge.trip_id

            s_from = network.stations[from_id]
            s_to = network.stations[edge.to_station_id]
            metrics = compute_leg_metrics(network.stations, from_id, edge)
            total_distance_km += metrics["distance_km"]
            total_co2_g += metrics["co2_g"]

            stage_legs_out.append({
                "from_station": s_from.name,
                "to_station": s_to.name,
                "departure": format_seconds_to_hhmm(edge.dep_sec),
                "arrival": format_seconds_to_hhmm(edge.arr_sec),
                "route": edge.route_name,
                "mode": metrics["mode"],
                "distance_km": metrics["distance_km"],
                "co2_g": metrics["co2_g"],
            })

            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[s_from.lon, s_from.lat], [s_to.lon, s_to.lat]]},
                "properties": {
                    "mode": "rail",
                    "train_type": metrics["mode"],
                    "from": s_from.name,
                    "to": s_to.name,
                    "departure": format_seconds_to_hhmm(edge.dep_sec),
                    "arrival": format_seconds_to_hhmm(edge.arr_sec),
                    "route": edge.route_name,
                },
            })

            is_transfer = (leg_i < len(legs) - 1) and (legs[leg_i + 1][1].trip_id != edge.trip_id)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s_to.lon, s_to.lat]},
                "properties": {
                    "name": s_to.name,
                    "role": "transfer" if is_transfer else "stop",
                    "detail": f"Arr {format_seconds_to_hhmm(edge.arr_sec)}",
                },
            })

        total_distance_km += walk_km
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[dest_st.lon, dest_st.lat], [poi.lon, poi.lat]]},
            "properties": {
                "mode": "walk",
                "from": dest_st.name,
                "to": poi.name,
                "distance_km": round(walk_km, 2),
                "duration_min": walk_sec // 60,
            },
        })
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [poi.lon, poi.lat]},
            "properties": {
                "name": f"POI {stage_idx + 1}: {poi.name}",
                "role": "poi",
                "detail": f"Arrivée {format_seconds_to_hhmm(arr_at_poi)}",
            },
        })

        stages.append({
            "stage": stage_idx + 1,
            "poi_name": poi.name,
            "arrival_station": dest_st.name,
            "poi_arrival_time": format_seconds_to_hhmm(arr_at_poi),
            "walk_km": round(walk_km, 2),
            "walk_min": walk_sec // 60,
            "rail_legs": stage_legs_out,
        })

        if stage_idx < len(req.pois) - 1:
            current_time_sec = arr_at_poi + (poi.visit_duration_min * 60) + walk_sec
            current_station = dest_st

    if journey_start_sec is None:
        journey_start_sec = base_dep_sec

    final_arrival_sec = parse_gtfs_time_to_seconds(f"{stages[-1]['poi_arrival_time']}:00")
    total_duration_min = max(0, (final_arrival_sec - journey_start_sec) // 60)
    car_co2_g = total_distance_km * CO2_G_PER_KM["CAR_BASELINE"]

    return {
        "summary": {
            "criterion": req.criterion,
            "date": req.date,
            "departure_time": format_seconds_to_hhmm(journey_start_sec),
            "final_arrival_time": stages[-1]["poi_arrival_time"],
            "total_duration_min": total_duration_min,
            "total_transfers": total_transfers,
            "total_distance_km": round(total_distance_km, 1),
            "total_co2_kg": round(total_co2_g / 1000.0, 2),
            "car_co2_kg": round(car_co2_g / 1000.0, 2),
            "co2_saved_kg": round(max(0.0, (car_co2_g - total_co2_g) / 1000.0), 2),
        },
        "initial_walk": initial_walk_info,
        "stages": stages,
        "geojson": {"type": "FeatureCollection", "features": features},
    }