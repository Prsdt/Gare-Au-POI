import csv
from collections import defaultdict
from pathlib import Path

data_folder = Path("DATA")
stops_files = list(data_folder.rglob("stops.txt"))

if not stops_files:
    raise FileNotFoundError("stops.txt not found")

stops_file = stops_files[0]

station_names = {}
station_to_points = defaultdict(list)

with open(stops_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        stop_id = row["stop_id"]
        loc_type = row["location_type"]
        parent_id = row["parent_station"]

        if loc_type == "1":
            station_names[stop_id] = row["stop_name"]
        elif loc_type == "0":
            station_to_points[parent_id].append(stop_id)

# Sort station areas by the number of stop points descending
sorted_stations = sorted(
    station_to_points.items(),
    key=lambda item: len(item[1]),
    reverse=True
)

print("========== STATIONS WITH MOST STOP POINTS ==========")
for station_id, points in sorted_stations[:5]:
    name = station_names.get(station_id, "Unknown Name")
    print(f"\nStation: {name} (ID: {station_id})")
    print(f"Total Stop Points: {len(points)}")
    for p in points:
        print(f"  - {p}")
print("\n====================================================")