import csv
from collections import Counter
from pathlib import Path

data_folder = Path("DATA")
routes_files = list(data_folder.rglob("routes.txt"))

if not routes_files:
    raise FileNotFoundError("routes.txt not found in DATA folder")

routes_file = routes_files[0]

total_routes = 0
route_types = Counter()
sample_routes = []

# GTFS standard route_type mapping
ROUTE_TYPE_MAP = {
    "0": "Tram, Streetcar, Light rail",
    "1": "Subway, Metro",
    "2": "Rail",
    "3": "Bus",
    "4": "Ferry",
    "7": "Funicular",
    "11": "Trolleybus",
    "12": "Monorail"
}

with open(routes_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    headers = reader.fieldnames

    for row in reader:
        total_routes += 1
        route_types[row.get("route_type", "unknown")] += 1
        if len(sample_routes) < 5:
            sample_routes.append(row)

print("========== ROUTES AUDIT ==========")
print(f"Total routes: {total_routes}")
print(f"Headers: {headers}")

print("\nBreakdown by Route Type:")
for r_type, count in route_types.items():
    desc = ROUTE_TYPE_MAP.get(r_type, "Other / Extended GTFS")
    print(f"  Type {r_type} ({desc}): {count}")

print("\nSample Routes:")
for r in sample_routes:
    print(f"  ID: {r.get('route_id')} | Short: {r.get('route_short_name')} | Long: {r.get('route_long_name')} | Type: {r.get('route_type')}")

print("==================================")