from app.engine.astar import haversine_km
from app.engine.graph import Station
from app.engine.timetable_router import TimetableEdge

# ADEME average emission factors (grams of CO2e per passenger-km)
CO2_G_PER_KM = {
    "TGV": 2.4,
    "INTERCITES": 9.0,
    "TER": 24.8,
    "WALK": 0.0,
    "CAR_BASELINE": 193.0,
}


def classify_train_mode(edge: TimetableEdge) -> str:
    """Infer commercial rail service type from GTFS trip_id or route_name."""
    text = f"{edge.trip_id} {edge.route_name}".upper()
    if "TGV" in text or "INOUI" in text or "OUIGO" in text or "LYRIA" in text:
        return "TGV"
    if "INTERCITES" in text or "180A" in text or "IC" in text:
        return "INTERCITES"
    return "TER"


def compute_leg_metrics(
    stations: dict[str, Station], from_id: str, edge: TimetableEdge
) -> dict:
    """Compute distance (km), mode, and CO2 emissions (g) for a single rail segment."""
    s_from = stations[from_id]
    s_to = stations[edge.to_station_id]
    # Rail track distance is typically ~1.15x straight-line Haversine distance
    dist_km = haversine_km(s_from.lat, s_from.lon, s_to.lat, s_to.lon) * 1.15
    mode = classify_train_mode(edge)
    co2_g = dist_km * CO2_G_PER_KM[mode]
    return {
        "mode": mode,
        "distance_km": round(dist_km, 2),
        "co2_g": round(co2_g, 1),
    }