import csv
from pathlib import Path

data_folder = Path("DATA")
stops_files = list(data_folder.rglob("stops.txt"))

if not stops_files:
    raise FileNotFoundError("stops.txt not found")

stops_file = stops_files[0]

station_areas = {}
stop_points = []

with open(stops_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        if row["location_type"] == "1":
            station_areas[row["stop_id"]] = row["stop_name"]

        elif row["location_type"] == "0":
            stop_points.append(row)

print("========== STATION HIERARCHY ==========")

displayed = 0

for point in stop_points:
    parent_id = point["parent_station"]

    if parent_id in station_areas:
        print(f"\nStation: {station_areas[parent_id]}")
        print(f"Station ID: {parent_id}")
        print(f"Stop point: {point['stop_name']}")
        print(f"Stop point ID: {point['stop_id']}")

        displayed += 1

    if displayed == 5:
        break

print("\n=======================================")