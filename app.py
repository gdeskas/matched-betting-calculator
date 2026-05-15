"""
Matched Betting Calculator with persistent SQLite log.

Run locally with:
    streamlit run app.py

Data is stored in matched_bets.db in the same directory.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st


DB_PATH = Path(__file__).parent / "matched_bets.db"


# ---------- Database layer ----------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                bet_date TEXT NOT NULL,
                bookie TEXT NOT NULL,
                event TEXT NOT NULL,
                selection TEXT NOT NULL,
                bet_type TEXT NOT NULL,
                stake REAL NOT NULL,
                back_odds REAL NOT NULL,
                lay_odds REAL NOT NULL,
                lay_stake REAL NOT NULL,
                liability REAL NOT NULL,
                commission REAL NOT NULL,
                profit_if_back_wins REAL NOT NULL,
                profit_if_lay_wins REAL NOT NULL,
                guaranteed_profit REAL NOT NULL,
                retention_pct REAL,
                notes TEXT,
                settled INTEGER DEFAULT 0,
                actual_outcome TEXT
            )
            """
        )


def insert_bet(record: dict) -> int:
    with get_db() as conn:
        cols = ", ".join(record.keys())
        placeholders = ", ".join(["?"] * len(record))
        cur = conn.execute(
            f"INSERT INTO bets ({cols}) VALUES ({placeholders})",
            tuple(record.values()),
        )
        return cur.lastrowid


def fetch_bets() -> pd.DataFrame:
    with get_db() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM bets ORDER BY bet_date DESC, id DESC", conn
        )
    return df


def delete_bet(bet_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,))


def mark_settled(bet_id: int, outcome: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE bets SET settled = 1, actual_outcome = ? WHERE id = ?",
            (outcome, bet_id),
        )


# ---------- Calculator ----------

@dataclass
class CalcResult:
    lay_stake: float
    liability: float
    profit_if_back_wins: float
    profit_if_lay_wins: float
    guaranteed: float
    rating_pct: float
    rating_label: str


def calculate(
    bet_type: str,
    stake: float,
    back_odds: float,
    lay_odds: float,
    commission: float,
) -> CalcResult:
    """
    bet_type: 'qualifying' | 'freebet_snr' | 'freebet_sr'
    commission: as decimal (0.02 for 2%)
    """
    if bet_type in ("qualifying", "freebet_sr"):
        lay_stake = (stake * back_odds) / (lay_odds - commission)
        liability = lay_stake * (lay_odds - 1)
        profit_back = stake * (back_odds - 1) - liability
        profit_lay = lay_stake * (1 - commission) - stake
        if bet_type == "freebet_sr":
            profit_back += stake
            profit_lay += stake
    elif bet_type == "freebet_snr":
        lay_stake = (stake * (back_odds - 1)) / (lay_odds - commission)
        liability = lay_stake * (lay_odds - 1)
        profit_back = stake * (back_odds - 1) - liability
        profit_lay = lay_stake * (1 - commission)
    else:
        raise ValueError(f"Unknown bet_type: {bet_type}")

    guaranteed = min(profit_back, profit_lay)

    if bet_type == "qualifying":
        rating_pct = abs(guaranteed / stake * 100) if stake else 0
        rating_label = f"{rating_pct:.1f}% {'profit' if guaranteed >= 0 else 'loss'} on stake"
    else:
        rating_pct = (guaranteed / stake * 100) if stake else 0
        rating_label = f"{rating_pct:.1f}% retention of free bet value"

    return CalcResult(
        lay_stake=round(lay_stake, 2),
        liability=round(liability, 2),
        profit_if_back_wins=round(profit_back, 2),
        profit_if_lay_wins=round(profit_lay, 2),
        guaranteed=round(guaranteed, 2),
        rating_pct=round(rating_pct, 1),
        rating_label=rating_label,
    )


# ---------- UI ----------

BET_TYPES = {
    "Qualifying bet (stake returned)": "qualifying",
    "Free bet — SNR (stake not returned)": "freebet_snr",
    "Free bet — SR (stake returned)": "freebet_sr",
}

BET_TYPE_LABELS = {v: k for k, v in BET_TYPES.items()}


def page_calculator() -> None:
    st.subheader("Calculator")

    col_type, col_comm = st.columns([2, 1])
    with col_type:
        bet_type_label = st.selectbox("Bet type", list(BET_TYPES.keys()))
        bet_type = BET_TYPES[bet_type_label]
    with col_comm:
        commission_pct = st.number_input(
            "Commission %", min_value=0.0, max_value=10.0, value=2.0, step=0.5
        )

    col_s, col_b, col_l = st.columns(3)
    with col_s:
        stake = st.number_input("Stake (£)", min_value=0.0, value=10.0, step=1.0)
    with col_b:
        back_odds = st.number_input("Back odds", min_value=1.01, value=2.0, step=0.01, format="%.2f")
    with col_l:
        lay_odds = st.number_input("Lay odds", min_value=1.01, value=2.04, step=0.01, format="%.2f")

    result = calculate(bet_type, stake, back_odds, lay_odds, commission_pct / 100)

    st.divider()

    m1, m2 = st.columns(2)
    m1.metric("Lay stake", f"£{result.lay_stake:.2f}")
    m2.metric("Liability", f"£{result.liability:.2f}")

    m3, m4 = st.columns(2)
    m3.metric("Profit if back wins", f"£{result.profit_if_back_wins:+.2f}")
    m4.metric("Profit if lay wins", f"£{result.profit_if_lay_wins:+.2f}")

    st.metric(
        "Guaranteed profit / qualifying loss",
        f"£{result.guaranteed:+.2f}",
        delta=result.rating_label,
        delta_color="normal" if result.guaranteed >= 0 else "inverse",
    )

    st.divider()
    st.subheader("Log this bet")

    with st.form("log_bet", clear_on_submit=True):
        col_d, col_book = st.columns(2)
        with col_d:
            bet_date = st.date_input("Date", value=date.today())
        with col_book:
            bookie = st.text_input("Bookie", placeholder="e.g. Betfred")

        event = st.text_input("Event", placeholder="e.g. England v Croatia")
        selection = st.text_input("Selection", placeholder="e.g. England to win")
        notes = st.text_area("Notes (optional)", height=80)

        submitted = st.form_submit_button("Add to log", type="primary")

        if submitted:
            if not bookie.strip() or not event.strip():
                st.error("Bookie and event are required.")
            else:
                record = {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "bet_date": bet_date.isoformat(),
                    "bookie": bookie.strip(),
                    "event": event.strip(),
                    "selection": selection.strip() or "—",
                    "bet_type": bet_type,
                    "stake": stake,
                    "back_odds": back_odds,
                    "lay_odds": lay_odds,
                    "lay_stake": result.lay_stake,
                    "liability": result.liability,
                    "commission": commission_pct / 100,
                    "profit_if_back_wins": result.profit_if_back_wins,
                    "profit_if_lay_wins": result.profit_if_lay_wins,
                    "guaranteed_profit": result.guaranteed,
                    "retention_pct": result.rating_pct,
                    "notes": notes.strip() or None,
                }
                bet_id = insert_bet(record)
                st.success(f"Logged bet #{bet_id}: {bookie} — {event}")


def page_log() -> None:
    st.subheader("Log")

    df = fetch_bets()

    if df.empty:
        st.info("No bets logged yet. Use the Calculator tab to add some.")
        return

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        bookie_filter = st.multiselect("Filter bookie", sorted(df["bookie"].unique()))
    with col_f2:
        type_filter = st.multiselect(
            "Filter type",
            sorted(df["bet_type"].unique()),
            format_func=lambda x: BET_TYPE_LABELS.get(x, x),
        )
    with col_f3:
        event_filter = st.text_input("Search event/selection")

    filtered = df.copy()
    if bookie_filter:
        filtered = filtered[filtered["bookie"].isin(bookie_filter)]
    if type_filter:
        filtered = filtered[filtered["bet_type"].isin(type_filter)]
    if event_filter:
        mask = (
            filtered["event"].str.contains(event_filter, case=False, na=False)
            | filtered["selection"].str.contains(event_filter, case=False, na=False)
        )
        filtered = filtered[mask]

    display = filtered[
        [
            "id", "bet_date", "bookie", "event", "selection",
            "bet_type", "stake", "back_odds", "lay_odds",
            "lay_stake", "liability", "guaranteed_profit",
        ]
    ].rename(columns={
        "bet_date": "Date",
        "bookie": "Bookie",
        "event": "Event",
        "selection": "Selection",
        "bet_type": "Type",
        "stake": "Stake",
        "back_odds": "Back",
        "lay_odds": "Lay",
        "lay_stake": "Lay £",
        "liability": "Liability",
        "guaranteed_profit": "Profit",
    })
    display["Type"] = display["Type"].map({
        "qualifying": "Qual", "freebet_snr": "FB-SNR", "freebet_sr": "FB-SR"
    }).fillna(display["Type"])
    display["Retention %"] = (display["Profit"] / display["Stake"] * 100).round(1)

    st.dataframe(
        display.set_index("id"),
        use_container_width=True,
        column_config={
            "Stake": st.column_config.NumberColumn(format="£%.2f"),
            "Lay £": st.column_config.NumberColumn(format="£%.2f"),
            "Liability": st.column_config.NumberColumn(format="£%.2f"),
            "Profit": st.column_config.NumberColumn(format="£%.2f"),
            "Retention %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.download_button(
        "Export filtered to CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"matched_bet_log_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

    st.divider()
    st.markdown("**Delete a bet**")
    col_id, col_btn = st.columns([1, 1])
    with col_id:
        del_id = st.number_input("Bet ID to delete", min_value=0, value=0, step=1)
    with col_btn:
        st.write("")
        if st.button("Delete", type="secondary"):
            if del_id > 0:
                delete_bet(int(del_id))
                st.success(f"Deleted bet #{del_id}")
                st.rerun()


def page_summary() -> None:
    st.subheader("Summary")

    df = fetch_bets()

    if df.empty:
        st.info("No data yet.")
        return

    total_profit = df["guaranteed_profit"].sum()
    qual_profit = df.loc[df["bet_type"] == "qualifying", "guaranteed_profit"].sum()
    fb_profit = df.loc[df["bet_type"] != "qualifying", "guaranteed_profit"].sum()
    total_stake = df["stake"].sum()
    total_liability = df["liability"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total profit", f"£{total_profit:+.2f}")
    c2.metric("Bets logged", len(df))
    c3.metric("Qualifying loss", f"£{qual_profit:+.2f}")
    c4.metric("Free bet profit", f"£{fb_profit:+.2f}")

    c5, c6 = st.columns(2)
    c5.metric("Total staked", f"£{total_stake:.2f}")
    c6.metric("Peak liability sum", f"£{total_liability:.2f}")

    st.divider()
    st.markdown("**By bookie**")
    by_bookie = (
        df.groupby("bookie")
        .agg(
            bets=("id", "count"),
            stake=("stake", "sum"),
            profit=("guaranteed_profit", "sum"),
        )
        .sort_values("profit", ascending=False)
        .reset_index()
    )
    by_bookie["retention"] = (by_bookie["profit"] / by_bookie["stake"] * 100).round(1)
    st.dataframe(
        by_bookie,
        use_container_width=True,
        column_config={
            "stake": st.column_config.NumberColumn(format="£%.2f"),
            "profit": st.column_config.NumberColumn(format="£%.2f"),
            "retention": st.column_config.NumberColumn(label="Retention %", format="%.1f%%"),
        },
        hide_index=True,
    )

    st.markdown("**By event**")
    by_event = (
        df.groupby("event")
        .agg(
            bets=("id", "count"),
            profit=("guaranteed_profit", "sum"),
        )
        .sort_values("profit", ascending=False)
        .reset_index()
    )
    st.dataframe(
        by_event,
        use_container_width=True,
        column_config={
            "profit": st.column_config.NumberColumn(format="£%.2f"),
        },
        hide_index=True,
    )

    st.markdown("**Cumulative profit over time**")
    timeline = df.sort_values("bet_date").copy()
    timeline["bet_date"] = pd.to_datetime(timeline["bet_date"])
    daily = timeline.groupby("bet_date")["guaranteed_profit"].sum().cumsum()
    st.line_chart(daily)


# ---------- Main ----------

def main() -> None:
    st.set_page_config(
        page_title="Matched Betting Calculator",
        page_icon="📊",
        layout="wide",
    )
    init_db()

    st.title("Matched Betting Calculator")
    st.caption("World Cup 2026 edition — local SQLite storage")

    tab1, tab2, tab3 = st.tabs(["Calculator", "Log", "Summary"])
    with tab1:
        page_calculator()
    with tab2:
        page_log()
    with tab3:
        page_summary()


if __name__ == "__main__":
    main()
