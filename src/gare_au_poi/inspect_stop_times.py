import csv
from pathlib import Path

data_folder = Path("DATA")
stop_times_files = list(data_folder.rglob("stop_times.txt"))

if not stop_times_files:
    raise FileNotFoundError("stop_times.txt not found in DATA folder")

stop_times_file = stop_times_files[0]

total_rows = 0
unique_trips = set()
unique_stops = set()
sample_rows = []
first_trip_sequence = []
first_trip_id = None

# Stream line-by-line without loading the 82 MB file into a single list
with open(stop_times_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    headers = reader.fieldnames

    for row in reader:
        total_rows += 1
        t_id = row["trip_id"]
        s_id = row["stop_id"]

        unique_trips.add(t_id)
        unique_stops.add(s_id)

        if first_trip_id is None:
            first_trip_id = t_id

        if t_id == first_trip_id:
            first_trip_sequence.append(row)

print("========== STOP TIMES AUDIT ==========")
print(f"Total stop_time records: {total_rows}")
print(f"Headers: {headers}")
print(f"Unique trips referenced: {len(unique_trips)}")
print(f"Unique stop_ids referenced: {len(unique_stops)}")

print(f"\nComplete Stop Sequence for First Trip ({first_trip_id}):")
for step in first_trip_sequence:
    print(
        f"  Seq {step['stop_sequence']}: {step['stop_id']} "
        f"| Arr: {step['arrival_time']} | Dep: {step['departure_time']}"
    )
print("======================================")