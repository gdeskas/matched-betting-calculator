# Matched Betting Calculator

A local Streamlit app for matched betting with persistent SQLite storage.
Built for the 2026 World Cup matched betting plan.

## Features

- **Calculator** — computes lay stake, liability, and guaranteed profit/loss for three bet types:
  - Qualifying bet (stake returned)
  - Free bet SNR (stake not returned) — the standard UK bookie offer
  - Free bet SR (stake returned)
- **Log** — record bets directly from the calculator with bookie, event, selection, and notes; filter by bookie, type, or event; export to CSV
- **Summary** — total profit, per-bookie and per-event breakdowns, cumulative profit chart over time
- **Persistent storage** — SQLite database survives restarts; back up by copying a single file

## Setup

Requires Python 3.10+. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
source .venv/bin/activate
streamlit run app.py
```

Opens at http://localhost:8501. The database `matched_bets.db` is created automatically on first run.

### Access from your phone on the same network

```bash
streamlit run app.py --server.address 0.0.0.0
```

Then visit `http://<your-mac-ip>:8501` from any device on your home network — useful for logging bets quickly while placing them.

## The maths

**Qualifying bets and stake-returned free bets:**

```
lay_stake = (stake × back_odds) / (lay_odds − commission)
```

**Stake-not-returned free bets:**

```
lay_stake = (stake × (back_odds − 1)) / (lay_odds − commission)
```

Liability is `lay_stake × (lay_odds − 1)`. Guaranteed profit is the minimum of the back-wins and lay-wins outcomes.

## Backup

The entire database is a single SQLite file:

```bash
cp matched_bets.db matched_bets_backup_$(date +%Y%m%d).db
```

You can also export any view to CSV from the Log tab.

## Querying the database directly

```python
import sqlite3, pandas as pd
df = pd.read_sql("SELECT * FROM bets", sqlite3.connect("matched_bets.db"))
```

## Database schema

```sql
CREATE TABLE bets (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at           TEXT NOT NULL,
    bet_date             TEXT NOT NULL,
    bookie               TEXT NOT NULL,
    event                TEXT NOT NULL,
    selection            TEXT NOT NULL,
    bet_type             TEXT NOT NULL,  -- 'qualifying' | 'freebet_snr' | 'freebet_sr'
    stake                REAL NOT NULL,
    back_odds            REAL NOT NULL,
    lay_odds             REAL NOT NULL,
    lay_stake            REAL NOT NULL,
    liability            REAL NOT NULL,
    commission           REAL NOT NULL,  -- decimal, e.g. 0.02 for 2%
    profit_if_back_wins  REAL NOT NULL,
    profit_if_lay_wins   REAL NOT NULL,
    guaranteed_profit    REAL NOT NULL,
    retention_pct        REAL,
    notes                TEXT,
    settled              INTEGER DEFAULT 0,
    actual_outcome       TEXT
);
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI |
| `pandas` | Data handling and display |

SQLite is part of the Python standard library — no extra install needed.
