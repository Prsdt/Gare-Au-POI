import csv
from pathlib import Path

data_folder = Path("DATA")
stops_files = list(data_folder.rglob("stops.txt"))

if not stops_files:
    raise FileNotFoundError("stops.txt not found")

stops_file = stops_files[0]

valid_coords = 0
invalid_coords = 0

lats = []
lons = []

with open(stops_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        try:
            lat = float(row["stop_lat"])
            lon = float(row["stop_lon"])
            lats.append(lat)
            lons.append(lon)
            valid_coords += 1
        except (ValueError, KeyError):
            invalid_coords += 1

print("========== COORDINATES AUDIT ==========")
print(f"Total valid coordinates: {valid_coords}")
print(f"Invalid or missing coordinates: {invalid_coords}")

if lats and lons:
    print(f"\nLatitude range:  [{min(lats):.6f}, {max(lats):.6f}]")
    print(f"Longitude range: [{min(lons):.6f}, {max(lons):.6f}]")

print("=======================================")