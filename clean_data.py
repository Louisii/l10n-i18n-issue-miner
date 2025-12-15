import csv
import os
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
from tqdm import tqdm

import sys
csv.field_size_limit(sys.maxsize)

# ---------------------------
# CONFIG
# ---------------------------

INPUT_DIR = Path("output")
OUTPUT_DIR = Path("cleaned_v2")
OUTPUT_DIR.mkdir(exist_ok=True)

LOG_FILE = OUTPUT_DIR / "cleaning_log.csv"
STATS_FILE = OUTPUT_DIR / "cleaning_stats.csv"

BUG_KEYWORDS = [
   # Generic bug indicators
    "bug", "fix", "error", "fail", "failure", "issue", "problem", 
    "broken", "incorrect", "wrong", "unexpected", "missing", 
    "lost", "typo", "properly", "failing", "failed", "does not work", 
    "doesn't work", "not working"
    # Translation-specific bugs
    "not translated", "wrong translation",  "missing translation", 
    "mistranslation",  "translation missing"
]

SEARCH_TERMS = [
    "i18n", "l10n", "localization", "internationalization", "translation",
    "missing translation", "mistranslation", "locale", "date format",
    "time format", "currency",
    "rtl", "right-to-left", "right to left",
    "wrong translation", "not translated", "text direction", "mirrored layout"
]

MIN_IMAGE_SIZE = 80  # px


# ---------------------------
# HELPERS
# ---------------------------

def contains_bug_keyword(text):
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in BUG_KEYWORDS)


def contains_valid_search_term(text):
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in SEARCH_TERMS)


def image_is_valid(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return False
        img = Image.open(BytesIO(resp.content))
        w, h = img.size
        return w > MIN_IMAGE_SIZE and h > MIN_IMAGE_SIZE
    except Exception:
        return False


def any_valid_image(urls_str):
    if not urls_str:
        return False
    urls = [u.strip() for u in urls_str.split(",") if u.strip()]
    return any(image_is_valid(url) for url in urls)


# ---------------------------
# MAIN CLEANING
# ---------------------------

def save_stats(counters):
    """Overwrites the stats file with current cumulative counters."""
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(counters.keys()))
        writer.writeheader()
        writer.writerow(counters)


def process_single_csv(csv_file: Path, log_writer, counters):
    print(f"\n➡️ Processing {csv_file.name}")

    cleaned_path = OUTPUT_DIR / f"cleaned_{csv_file.name}"
    valid_rows = []
    total_before = 0

    with open(csv_file, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

        for row in tqdm(reader, desc=f"Cleaning {csv_file.name}", unit="issue"):
            total_before += 1
            counters["total_scanned"] += 1

            issue_id = row.get("issue_id", "")
            title = row.get("title", "")
            body = row.get("body", "")
            labels = row.get("labels", "")

            combined_text = f"{title} {body} {labels}".lower()

            # RULE 1 — bug keyword
            if not contains_bug_keyword(combined_text):
                counters["removed_bug_keyword"] += 1
                log_writer.writerow({
                    "issue_id": issue_id,
                    "csv_file": csv_file.name,
                    "removed_by": "bug_keyword",
                    "title": title
                })
                save_stats(counters)
                continue

            # RULE 2 — search term
            if not contains_valid_search_term(combined_text):
                counters["removed_search_term"] += 1
                log_writer.writerow({
                    "issue_id": issue_id,
                    "csv_file": csv_file.name,
                    "removed_by": "search_term",
                    "title": title
                })
                save_stats(counters)
                continue

            # RULE 3 — valid image
            urls = row.get("image_urls", "")
            if not any_valid_image(urls):
                counters["removed_image"] += 1
                log_writer.writerow({
                    "issue_id": issue_id,
                    "csv_file": csv_file.name,
                    "removed_by": "image",
                    "title": title
                })
                save_stats(counters)
                continue

            # If passed all checks → keep
            counters["kept"] += 1
            log_writer.writerow({
                "issue_id": issue_id,
                "csv_file": csv_file.name,
                "removed_by": "kept",
                "title": title
            })

            valid_rows.append(row)
            save_stats(counters)

    print(f"🧹 {len(valid_rows)} valid issues (from {total_before}) in {csv_file.name}")

    # Save cleaned CSV
    if valid_rows:
        fieldnames = [c for c in valid_rows[0].keys() if c != "body"]

        with open(cleaned_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in valid_rows:
                row.pop("body", None)
                writer.writerow(row)

        print(f"💾 Saved cleaned file: {cleaned_path.name}")
    else:
        print(f"⚠️ No valid issues for {csv_file.name}")


def main():
    csv_files = sorted(INPUT_DIR.glob("*.csv"))
    if not csv_files:
        print("❌ No CSVs found in output/")
        return

    print(f"📂 Found {len(csv_files)} CSV files")

    # counters
    counters = {
        "total_scanned": 0,
        "kept": 0,
        "removed_bug_keyword": 0,
        "removed_search_term": 0,
        "removed_image": 0
    }

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as lf:
        log_writer = csv.DictWriter(
            lf, fieldnames=["issue_id", "csv_file", "removed_by", "title"]
        )
        log_writer.writeheader()

        for csv_file in csv_files:
            process_single_csv(csv_file, log_writer, counters)

    print(f"\n📄 Log saved at: {LOG_FILE}")
    print(f"📊 Stats saved at: {STATS_FILE}")


if __name__ == "__main__":
    main()