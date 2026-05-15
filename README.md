# Matched Betting Calculator

A local Streamlit app for matched betting with persistent SQLite storage.
Built for the 2026 World Cup matched betting plan.

## Features

- **Calculator** for three bet types: qualifying bet, free bet SNR (stake not returned), free bet SR (stake returned)
- **Persistent log** in SQLite — survives restarts, easy to back up (just copy `matched_bets.db`)
- **Summary** with per-bookie and per-event breakdowns, cumulative profit chart
- **CSV export** for analysis in pandas / Excel / wherever
- **Filters** on the log view by bookie, type, event search

## Setup (one-time)

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

Opens at http://localhost:8501. The database `matched_bets.db` is created
automatically on first run in the same folder as `app.py`.

## Accessing from your phone on the same network

```bash
streamlit run app.py --server.address 0.0.0.0
```

Then visit `http://<your-mac-ip>:8501` from any device on your home network.
Useful for logging bets quickly from your phone while you're placing them.

## The maths

For qualifying bets and stake-returned free bets:

    lay_stake = (stake × back_odds) / (lay_odds − commission)

For stake-not-returned free bets (the standard UK bookie offer):

    lay_stake = (stake × (back_odds − 1)) / (lay_odds − commission)

Liability is `lay_stake × (lay_odds − 1)`. The guaranteed profit is the
minimum of the back-wins and lay-wins outcomes.

## Backup

The database is a single SQLite file. To back up:

```bash
cp matched_bets.db matched_bets_backup_$(date +%Y%m%d).db
```

Or restore from a CSV export with the Log tab's import (not yet built — let
me know if you want it).

## Schema

```sql
CREATE TABLE bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    bet_date TEXT,
    bookie TEXT,
    event TEXT,
    selection TEXT,
    bet_type TEXT,        -- 'qualifying' | 'freebet_snr' | 'freebet_sr'
    stake REAL,
    back_odds REAL,
    lay_odds REAL,
    lay_stake REAL,
    liability REAL,
    commission REAL,      -- decimal, e.g. 0.02 for 2%
    profit_if_back_wins REAL,
    profit_if_lay_wins REAL,
    guaranteed_profit REAL,
    notes TEXT,
    settled INTEGER,
    actual_outcome TEXT
);
```

Easy to query directly:

```python
import sqlite3, pandas as pd
df = pd.read_sql("SELECT * FROM bets", sqlite3.connect("matched_bets.db"))
```
