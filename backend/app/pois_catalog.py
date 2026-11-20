from app.engine.poi_planner import PointOfInterest

CATALOG_POIS: list[dict] = [
    {"id": "vieux-port", "name": "Vieux-Port de Marseille", "city": "Marseille", "lat": 43.2951, "lon": 5.3744},
    {"id": "notre-dame-garde", "name": "Basilique Notre-Dame de la Garde", "city": "Marseille", "lat": 43.2840, "lon": 5.3712},
    {"id": "tour-eiffel", "name": "Tour Eiffel", "city": "Paris", "lat": 48.8584, "lon": 2.2945},
    {"id": "louvre", "name": "Musée du Louvre", "city": "Paris", "lat": 48.8606, "lon": 2.3376},
    {"id": "cite-vin", "name": "La Cité du Vin", "city": "Bordeaux", "lat": 44.8624, "lon": -0.5506},
    {"id": "miroir-eau", "name": "Place de la Bourse & Miroir d'Eau", "city": "Bordeaux", "lat": 44.8412, "lon": -0.5699},
    {"id": "bellecour", "name": "Place Bellecour", "city": "Lyon", "lat": 45.7578, "lon": 4.8320},
    {"id": "fourviere", "name": "Basilique Notre-Dame de Fourvière", "city": "Lyon", "lat": 45.7623, "lon": 4.8226},
    {"id": "cathedrale-strasbourg", "name": "Cathédrale Notre-Dame de Strasbourg", "city": "Strasbourg", "lat": 48.5818, "lon": 7.7509},
    {"id": "promenade-anglais", "name": "Promenade des Anglais", "city": "Nice", "lat": 43.6947, "lon": 7.2653},
    {"id": "capitole", "name": "Place du Capitole", "city": "Toulouse", "lat": 43.6045, "lon": 1.4440},
    {"id": "comedie", "name": "Place de la Comédie", "city": "Montpellier", "lat": 43.6085, "lon": 3.8797},
]


def to_poi_dataclass(name: str, lat: float, lon: float) -> PointOfInterest:
    return PointOfInterest(name=name, lat=lat, lon=lon)