import requests
import csv
import json
import re
import os
from time import sleep
from datetime import datetime, timedelta
from collections import Counter
from dotenv import load_dotenv
from pathlib import Path
import argparse

# 
# EXEMPLO:
# python mine_issues.py --start-year 2020 --end-year 2025 --interval-days 30 --max-pages 1 --per-page 10
#

load_dotenv()  # Load .env variables

# -----------------------------
# CONFIGURAÇÃO PADRÃO
# -----------------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

SEARCH_TERMS = [
    "i18n", "l10n", "localization", "internationalization", "translation",
    "missing translation", "mistranslation", "locale", "date format",
    "time format", "currency",
    "rtl", "right-to-left",
    "wrong translation", "not translated", "text direction", "mirrored layout"
]

CSV_OUTPUT_TEMPLATE = "l10n_i18n_issues_{year}_Q{quarter}.csv"
JSON_OUTPUT_TEMPLATE = "l10n_i18n_issues_{year}_Q{quarter}.json"

BUG_TYPES = {
    "truncation": ["truncate", "truncated", "cut off", "clipping", "overflow"],
    "missing_translation": ["missing translation", "not translated", "no translation"],
    "mistranslation": ["wrong translation", "incorrect translation", "mistranslation"],
    "locale_issue": ["locale", "region", "timezone", "date format", "time format"],
    "overlap_ui": ["overlap", "misalignment", "layout issue", "UI issue"],
    "encoding": ["encoding", "utf-8", "unicode", "character set"],
    "rtl_issue": ["rtl", "right-to-left", "bidirectional", "bidi", "text direction", "mirrored layout"]
}

DATE_INTERVAL_DAYS = 30
MAX_PAGES = 1
RESULTS_PER_PAGE = 10
START_YEAR = 2025
END_YEAR = 2015


# -----------------------------
# FUNÇÕES
# -----------------------------
def extract_image_urls(text):
    if not text:
        return []
    # Pega apenas URLs terminando com png, jpg, jpeg, gif ou webp
    pattern = r'https?://[^\s")]+?\.(?:png|jpg|jpeg|gif|webp)'
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    return matches



def detect_bug_types(title, body):
    text = f"{title or ''} {body or ''}".lower()
    return [bug_type for bug_type, keywords in BUG_TYPES.items() if any(k in text for k in keywords)]


def detect_search_terms(text, term):
    found_terms = [t for t in SEARCH_TERMS if t.lower() in (text or "").lower()]
    if term not in found_terms:
        found_terms.append(term)
    return found_terms


def fetch_issue_comments(comments_url):
    try:
        response = requests.get(comments_url, headers=HEADERS)
        if response.status_code != 200:
            return []
        comments = response.json()
        images = []
        for c in comments:
            images.extend(extract_image_urls(c.get("body", "")))
        return images
    except Exception:
        return []


def fetch_issues_by_date(term, since_date, until_date):
    issues = []
    for page in range(1, MAX_PAGES + 1):
        query = f'{term} in:title,body is:issue created:{since_date}..{until_date}'
        url = "https://api.github.com/search/issues"
        params = {"q": query, "page": page, "per_page": RESULTS_PER_PAGE}
        print(f"  🔎 Fetching page {page} for term '{term}' from {since_date} → {until_date}")

        try:
            response = requests.get(url, headers=HEADERS, params=params)
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Connection error: {e}")
            continue

        if response.status_code == 403:
            print("⚠️ Rate limit reached. Waiting 60s...")
            sleep(60)
            continue

        if response.status_code != 200:
            break

        items = response.json().get("items", [])
        if not items:
            break

        for item in items:
            body = item.get("body") or ""
            images = extract_image_urls(body)
            images += fetch_issue_comments(item.get("comments_url"))

            repo_full_name = item["repository_url"].split("repos/")[-1]
            text = f"{item.get('title', '')} {body}"

            issues.append({
                "issue_id": item.get("id"),
                "repo_full": repo_full_name,
                "repo": repo_full_name.split("/")[-1],
                "title": item.get("title"),
                "url": item.get("html_url"),
                "body": body,
                "labels": [label["name"] for label in item.get("labels", [])],
                "image_urls": images,
                "bug_types": detect_bug_types(item.get("title"), body),
                "search_terms_found": detect_search_terms(text, term),
                "created_at": item.get("created_at")
            })

        sleep(1)

    return issues


def save_to_csv(issues, filename):
    keys = [
        "issue_id", "repo_full", "repo", "title", "body", "url",
        "labels", "image_urls", "bug_types", "search_terms_found", "created_at"
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()

        for issue in issues:
            writer.writerow({
                "issue_id": issue["issue_id"],
                "repo_full": issue["repo_full"],
                "repo": issue["repo"],
                "title": issue["title"],
                "body": issue["body"],
                "url": issue["url"],
                "labels": ", ".join(issue["labels"]),
                "image_urls": ", ".join(issue["image_urls"]),
                "bug_types": ", ".join(issue["bug_types"]),
                "search_terms_found": ", ".join(issue["search_terms_found"]),
                "created_at": issue["created_at"]
            })


def save_to_json(issues, filename, total_collected, search_terms, search_type="date-based"):
    bugtype_counter = Counter(tag for issue in issues for tag in issue["bug_types"])
    local_time = datetime.now().astimezone().isoformat(timespec="seconds")

    summary = {
        "fetched_at": local_time,
        "counts": {
            "total_collected": total_collected,
            "total_saved": len(issues),
            "bugtype_counts": dict(bugtype_counter)
        },
        "search_setup": {
            "script": "v3",
            "search_type": search_type,
            "search_terms": search_terms,
            "date_interval_days": DATE_INTERVAL_DAYS
        }
    }

    output = {"summary": summary, "issues": issues}

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


# -----------------------------
# MAIN
# -----------------------------
def main():
    global START_YEAR, END_YEAR, DATE_INTERVAL_DAYS, MAX_PAGES, RESULTS_PER_PAGE

    parser = argparse.ArgumentParser(description="GitHub L10n/i18n issue miner")

    parser.add_argument("--start-year", "-s", type=int, default=START_YEAR)
    parser.add_argument("--end-year", "-e", type=int, default=END_YEAR)
    parser.add_argument("--interval-days", "-i", type=int, default=DATE_INTERVAL_DAYS)
    parser.add_argument("--max-pages", "-mp", type=int, default=MAX_PAGES)
    parser.add_argument("--per-page", "-pp", type=int, default=RESULTS_PER_PAGE)
    parser.add_argument("--start-quarter", type=int, default=1)

    args = parser.parse_args()

    START_YEAR = args.start_year
    END_YEAR = args.end_year
    DATE_INTERVAL_DAYS = args.interval_days
    MAX_PAGES = args.max_pages
    RESULTS_PER_PAGE = args.per_page

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    if GITHUB_TOKEN:
        print("🔑 Using GitHub token")
    else:
        print("🚨 No GitHub token — rate limits will be VERY low")

    today = datetime.utcnow()

    # ===========================================================
    # PROCESSA OS ANOS EM ORDEM DECRESCENTE
    # ===========================================================
    for year in range(END_YEAR, START_YEAR - 1, -1):
        print(f"\n📆 Processing year {year}...")

        quarters = [
            (1, 3),   # Q1
            (4, 6),   # Q2
            (7, 9),   # Q3
            (10, 12)  # Q4
        ]

        for q_index, (m_start, m_end) in enumerate(quarters, start=1):

            if q_index < args.start_quarter:
                continue

            q_start = datetime(year, m_start, 1)
            q_end = datetime(year, m_end, 1)

            # último dia do mês final
            if m_end in [1,3,5,7,8,10,12]:
                last_day = 31
            elif m_end == 2:
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    last_day = 29
                else:
                    last_day = 28
            else:
                last_day = 30

            q_end = datetime(year, m_end, last_day)

            if q_start > today:
                break

            print(f"\n🗓️  Processing Q{q_index} ({q_start:%b}–{q_end:%b}) {year}...")

            current_start = q_end
            seen_urls = set()
            quarter_issues = []

            while current_start >= q_start:
                current_end = current_start
                interval_start = max(q_start, current_start - timedelta(days=DATE_INTERVAL_DAYS - 1))

                since_str = interval_start.strftime("%Y-%m-%d")
                until_str = current_end.strftime("%Y-%m-%d")

                for term in SEARCH_TERMS:
                    issues = fetch_issues_by_date(term, since_str, until_str)
                    for issue in issues:
                        if issue["url"] not in seen_urls:
                            seen_urls.add(issue["url"])
                            quarter_issues.append(issue)

                current_start = interval_start - timedelta(days=1)

            issues_with_images = [i for i in quarter_issues if i["image_urls"]]

            csv_path = output_dir / CSV_OUTPUT_TEMPLATE.format(year=year, quarter=q_index)
            json_path = output_dir / JSON_OUTPUT_TEMPLATE.format(year=year, quarter=q_index)

            save_to_csv(issues_with_images, csv_path)
            save_to_json(
                issues_with_images,
                json_path,
                total_collected=len(quarter_issues),
                search_terms=SEARCH_TERMS
            )

            print(f"💾 Saved Q{q_index}: {csv_path}, {json_path}")

    print("\n✅ Finished. All files saved in /output")


if __name__ == "__main__":
    main()
