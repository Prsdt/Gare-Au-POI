import csv
from collections import Counter
from pathlib import Path

data_folder = Path("DATA")
trips_files = list(data_folder.rglob("trips.txt"))

if not trips_files:
    raise FileNotFoundError("trips.txt not found in DATA folder")

trips_file = trips_files[0]

total_trips = 0
trips_per_route = Counter()
unique_services = set()
sample_trips = []

with open(trips_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    headers = reader.fieldnames

    for row in reader:
        total_trips += 1
        trips_per_route[row["route_id"]] += 1
        if "service_id" in row:
            unique_services.add(row["service_id"])
        if len(sample_trips) < 5:
            sample_trips.append(row)

print("========== TRIPS AUDIT ==========")
print(f"Total trips: {total_trips}")
print(f"Headers: {headers}")
print(f"Routes with at least one trip: {len(trips_per_route)}")
print(f"Unique service_ids (calendars): {len(unique_services)}")

print("\nTop 5 Routes by Number of Trips:")
for r_id, count in trips_per_route.most_common(5):
    print(f"  Route {r_id}: {count} trips")

print("\nSample Trips:")
for t in sample_trips:
    print(f"  Trip ID: {t.get('trip_id')} | Route ID: {t.get('route_id')} | Headsign: {t.get('trip_headsign')} | Direction: {t.get('direction_id')}")

print("=================================")