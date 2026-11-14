from pathlib import Path

data_folder = Path("DATA")
all_txt_files = sorted(data_folder.rglob("*.txt"))

print("========== ALL GTFS FILES FOUND ==========")
for f in all_txt_files:
    print(f"  {f.name:<22} | {f.stat().st_size:>10,} bytes")

print("\n========== SMALL FILES CONTENT ==========")
for f in all_txt_files:
    # Print full content of small metadata/transfer files (< 5 KB)
    if f.stat().st_size < 5000:
        print(f"\n--- {f.name} ---")
        print(f.read_text(encoding="utf-8-sig").strip())
print("\n=========================================")