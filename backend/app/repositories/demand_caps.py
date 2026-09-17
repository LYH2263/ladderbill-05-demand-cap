import sqlite3

COLS = "id, account_id, period, demand_kw, threshold_kw, conversion_factor, updated_at"


def _row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "period": row["period"],
        "demand_kw": row["demand_kw"],
        "threshold_kw": row["threshold_kw"],
        "conversion_factor": row["conversion_factor"],
        "updated_at": row["updated_at"],
    }


def for_account(conn: sqlite3.Connection, account_id: int) -> list[dict]:
    q = f"SELECT {COLS} FROM demand_caps WHERE account_id=? ORDER BY period DESC"
    return [_row(r) for r in conn.execute(q, (account_id,)).fetchall()]


def get(conn: sqlite3.Connection, account_id: int, period: str) -> dict | None:
    q = f"SELECT {COLS} FROM demand_caps WHERE account_id=? AND period=?"
    row = conn.execute(q, (account_id, period)).fetchone()
    return _row(row) if row else None


def upsert(
    conn: sqlite3.Connection,
    account_id: int,
    period: str,
    demand_kw: float,
    threshold_kw: float,
    conversion_factor: float,
) -> dict:
    """Insert or update the cap for an account/period; returns the stored row."""
    existing = get(conn, account_id, period)
    if existing:
        conn.execute(
            """
            UPDATE demand_caps
               SET demand_kw=?, threshold_kw=?, conversion_factor=?, updated_at=datetime('now')
             WHERE id=?
            """,
            (demand_kw, threshold_kw, conversion_factor, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO demand_caps(account_id, period, demand_kw, threshold_kw, conversion_factor, updated_at)
            VALUES (?,?,?,?,?,datetime('now'))
            """,
            (account_id, period, demand_kw, threshold_kw, conversion_factor),
        )
    conn.commit()
    return get(conn, account_id, period)
