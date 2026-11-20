
import csv
from pathlib import Path

# 1. Locate the GTFS stops file
data_folder = Path("DATA")
stops_files = list(data_folder.rglob("stops.txt"))

if not stops_files:
    raise FileNotFoundError("stops.txt not found")

stops_file = stops_files[0]

# 2. Initialize counters
total_records = 0
unique_ids = set()

station_areas = 0
stop_points = 0

missing_values = {}

# 3. Read and analyze the dataset
with open(stops_file, "r", encoding="utf-8-sig", newline="") as file:

    reader = csv.DictReader(file)

    columns = reader.fieldnames

    for row in reader:

        total_records += 1

        unique_ids.add(row["stop_id"])

        if row["location_type"] == "1":
            station_areas += 1

        elif row["location_type"] == "0":
            stop_points += 1

        # Count missing values
        for column in columns:
            if not row[column].strip():
                missing_values[column] = missing_values.get(column, 0) + 1


# 4. Display results
print("\n========== GTFS DATA PROFILING ==========")

print(f"Total records: {total_records}")
print(f"Unique stop IDs: {len(unique_ids)}")

print(f"Station areas: {station_areas}")
print(f"Stop points: {stop_points}")

print("\nMissing values:")

for column, count in missing_values.items():
    print(f"{column}: {count}")

print("\n=========================================")
