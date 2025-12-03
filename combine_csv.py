import csv
from pathlib import Path
import sys

# Corrige limite de tamanho CSV
csv.field_size_limit(sys.maxsize)

# -----------------------------
# Config
# -----------------------------
OUTPUT_DIR = Path("output")
MERGED_FILE = OUTPUT_DIR / "merged_issues.csv"

csv_files = list(OUTPUT_DIR.glob("*.csv"))
if not csv_files:
    print("❌ No CSV files found in output/")
    exit(1)

print(f"📄 Merging {len(csv_files)} CSV files...")

merged_rows = []
all_fieldnames = set()

# -----------------------------
# Coleta linhas e colunas
# -----------------------------
for csv_file in csv_files:
    print(f" - Reading {csv_file.name}")
    try:
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue

            # Atualiza o conjunto de colunas ignorando 'body'
            cols = [col for col in reader.fieldnames if col != "body"]
            all_fieldnames.update(cols)

            for row in reader:
                # Remove 'body' da linha
                if "body" in row:
                    del row["body"]
                merged_rows.append(row)

    except Exception as e:
        print(f"❌ Error reading {csv_file.name}: {e}")

# Ordena colunas (opcional)
all_fieldnames = list(all_fieldnames)

# -----------------------------
# Salva CSV único
# -----------------------------
print(f"💾 Writing merged CSV to {MERGED_FILE.name} ...")
try:
    with open(MERGED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fieldnames)
        writer.writeheader()
        writer.writerows(merged_rows)
    print(f"✅ Merged CSV created: {MERGED_FILE.name}")
except Exception as e:
    print(f"❌ Error writing merged CSV: {e}")
