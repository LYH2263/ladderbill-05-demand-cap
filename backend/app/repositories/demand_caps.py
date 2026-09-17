import sqlite3
from datetime import datetime, timezone


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "account_id": row["account_id"],
        "period": row["period"],
        "demand_kw": row["demand_kw"],
        "cap_kw": row["cap_kw"],
        "convert_coef": row["convert_coef"],
        "updated_at": row["updated_at"],
    }


def get(conn: sqlite3.Connection, account_id: int, period: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM demand_caps WHERE account_id=? AND period=?",
        (account_id, period),
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_for_account(conn: sqlite3.Connection, account_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM demand_caps WHERE account_id=? ORDER BY period DESC",
        (account_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def upsert(
    conn: sqlite3.Connection,
    account_id: int,
    period: str,
    demand_kw: float,
    cap_kw: float,
    convert_coef: float,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO demand_caps(account_id, period, demand_kw, cap_kw, convert_coef, updated_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(account_id, period) DO UPDATE SET
            demand_kw=excluded.demand_kw,
            cap_kw=excluded.cap_kw,
            convert_coef=excluded.convert_coef,
            updated_at=excluded.updated_at
        """,
        (account_id, period, demand_kw, cap_kw, convert_coef, now),
    )
    conn.commit()
    return get(conn, account_id, period)
