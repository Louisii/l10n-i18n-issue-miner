# GitHub Issues Miner

A Python script that collects GitHub issues in time-based intervals and
saves them as CSV and JSON files.

## 🔧 Setup

1.  Create a `.env` file in the project root:

        GITHUB_TOKEN=your_github_token_here

2.  Install dependencies:

        pip install -r requirements.txt

    or

        python -m pip install -r requirements.txt

## ▶️ Usage

Run the script with your desired parameters:

    python mine_issues.py   --start-year 2020   --end-year 2025   --interval-days 15   --max-pages 10   --per-page 100

Outputs are saved inside the `output/` directory (ignored by Git).
