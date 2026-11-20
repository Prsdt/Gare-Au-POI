import csv
from collections import Counter
from pathlib import Path

data_folder = Path("DATA")
cal_files = list(data_folder.rglob("calendar_dates.txt"))

if not cal_files:
    raise FileNotFoundError("calendar_dates.txt not found in DATA folder")

cal_file = cal_files[0]

total_rows = 0
exception_types = Counter()
unique_services = set()
dates = set()
sample_rows = []

with open(cal_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    headers = reader.fieldnames

    for row in reader:
        total_rows += 1
        unique_services.add(row["service_id"])
        dates.add(row["date"])
        exception_types[row["exception_type"]] += 1

        if len(sample_rows) < 5:
            sample_rows.append(row)

print("========== CALENDAR DATES AUDIT ==========")
print(f"Total calendar_dates records: {total_rows}")
print(f"Headers: {headers}")
print(f"Unique service_ids: {len(unique_services)}")
print(f"Total distinct operating dates: {len(dates)}")

if dates:
    print(f"Date range: {min(dates)} -> {max(dates)}")

print("\nBreakdown by exception_type:")
for exc_type, count in exception_types.items():
    label = "Added (runs on date)" if exc_type == "1" else "Removed (does not run)" if exc_type == "2" else "Other"
    print(f"  Type {exc_type} ({label}): {count}")

print("\nSample Records:")
for r in sample_rows:
    print(f"  Service: {r['service_id']} | Date: {r['date']} | Exception Type: {r['exception_type']}")

print("==========================================")