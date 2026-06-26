import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "require"),
    )


def _to_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def create_portfolio_table() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_portfolio (
                    portfolio_id BIGSERIAL PRIMARY KEY,
                    user_id VARCHAR(20) NOT NULL,
                    investor_name VARCHAR(100) NOT NULL,
                    risk_profile VARCHAR(20),
                    scheme_code VARCHAR(20),
                    scheme_name VARCHAR(200),
                    units NUMERIC(12,2),
                    purchase_nav NUMERIC(10,2),
                    current_nav NUMERIC(10,2),
                    invested_amount NUMERIC(15,2),
                    current_value NUMERIC(15,2),
                    purchase_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()


def seed_portfolio_data() -> int:
    create_portfolio_table()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM user_portfolio")
            count = cursor.fetchone()[0]
            if count >= 100:
                return int(count)

            investor_names = [
                f"Investor {index + 1:02d}"
                for index in range(50)
            ]
            risk_profiles = ["Conservative"] * 15 + ["Moderate"] * 20 + ["Aggressive"] * 15
            funds = [
                ("1001", "SBI Bluechip Fund"),
                ("1002", "Parag Parikh Flexi Cap Fund"),
                ("1003", "HDFC Mid Cap Opportunities Fund"),
                ("1004", "Axis Small Cap Fund"),
                ("1005", "ICICI Prudential Value Discovery Fund"),
                ("1006", "Nippon India Growth Fund"),
                ("1007", "Mirae Asset Emerging Bluechip Fund"),
                ("1008", "UTI Nifty 50 Index Fund"),
                ("1009", "Kotak Emerging Equity Fund"),
                ("1010", "Quant Small Cap Fund"),
            ]

            for investor_index in range(50):
                user_id = f"U{investor_index + 1:03d}"
                investor_name = investor_names[investor_index]
                risk_profile = risk_profiles[investor_index]
                for holding_index in range(2):
                    scheme_code, scheme_name = funds[(investor_index + holding_index) % len(funds)]
                    units = Decimal((investor_index % 5 + 1) * 100 + (holding_index + 1) * 50)
                    purchase_nav = Decimal(35 + ((investor_index + holding_index) % 10) * 5 + (holding_index * 1.5))
                    current_nav = purchase_nav * Decimal(1 + ((investor_index + holding_index) % 6) * 0.04 + 0.01)
                    invested_amount = units * purchase_nav
                    current_value = units * current_nav
                    purchase_date = date(2023, 1, 10) + timedelta(days=(investor_index * 11 + holding_index * 7) % 300)

                    cursor.execute(
                        """
                        INSERT INTO user_portfolio (
                            user_id, investor_name, risk_profile, scheme_code, scheme_name,
                            units, purchase_nav, current_nav, invested_amount, current_value, purchase_date
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            investor_name,
                            risk_profile,
                            scheme_code,
                            scheme_name,
                            units,
                            purchase_nav,
                            current_nav,
                            invested_amount,
                            current_value,
                            purchase_date,
                        ),
                    )
            conn.commit()
            return 100


def create_portfolio_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    create_portfolio_table()
    data = dict(payload)
    units = Decimal(str(data.get("units")))
    purchase_nav = Decimal(str(data.get("purchase_nav")))
    current_nav = data.get("current_nav")
    if current_nav is None:
        current_nav = purchase_nav
    else:
        current_nav = Decimal(str(current_nav))

    invested_amount = data.get("invested_amount")
    if invested_amount is None:
        invested_amount = units * purchase_nav
    else:
        invested_amount = Decimal(str(invested_amount))

    current_value = data.get("current_value")
    if current_value is None:
        current_value = units * current_nav
    else:
        current_value = Decimal(str(current_value))

    purchase_date = data.get("purchase_date")

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_portfolio (
                    user_id, investor_name, risk_profile, scheme_code, scheme_name,
                    units, purchase_nav, current_nav, invested_amount, current_value, purchase_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING portfolio_id, user_id, investor_name, risk_profile, scheme_code, scheme_name,
                          units, purchase_nav, current_nav, invested_amount, current_value, purchase_date, created_at
                """,
                (
                    data.get("user_id"),
                    data.get("investor_name"),
                    data.get("risk_profile"),
                    data.get("scheme_code"),
                    data.get("scheme_name"),
                    units,
                    purchase_nav,
                    current_nav,
                    invested_amount,
                    current_value,
                    purchase_date,
                ),
            )
            row = cursor.fetchone()
            conn.commit()

    if row is None:
        raise RuntimeError("Portfolio record was not created")

    columns = [
        "portfolio_id",
        "user_id",
        "investor_name",
        "risk_profile",
        "scheme_code",
        "scheme_name",
        "units",
        "purchase_nav",
        "current_nav",
        "invested_amount",
        "current_value",
        "purchase_date",
        "created_at",
    ]
    return {key: _serialize_value(value) for key, value in zip(columns, row)}


def get_portfolio_by_user(user_id: str) -> Dict[str, Any]:
    create_portfolio_table()
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT portfolio_id, user_id, investor_name, risk_profile, scheme_code, scheme_name,
                       units, purchase_nav, current_nav, invested_amount, current_value, purchase_date, created_at
                FROM user_portfolio
                WHERE user_id = %s
                ORDER BY purchase_date, scheme_name
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

    holdings: List[Dict[str, Any]] = []
    for row in rows:
        portfolio_id, user_id_value, investor_name, risk_profile, scheme_code, scheme_name, units, purchase_nav, current_nav, invested_amount, current_value, purchase_date, created_at = row
        invested_amount_value = float(invested_amount or 0)
        current_value_value = float(current_value or 0)
        profit_loss = round(current_value_value - invested_amount_value, 2)
        gain_pct = round((profit_loss / invested_amount_value) * 100, 1) if invested_amount_value else 0.0
        holdings.append(
            {
                "portfolio_id": portfolio_id,
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "units": float(units) if units is not None else None,
                "purchase_nav": float(purchase_nav) if purchase_nav is not None else None,
                "current_nav": float(current_nav) if current_nav is not None else None,
                "invested_amount": float(invested_amount_value),
                "current_value": float(current_value_value),
                "profit_loss": profit_loss,
                "gain_pct": gain_pct,
                "purchase_date": purchase_date.isoformat() if purchase_date else None,
            }
        )

    return {
        "user_id": user_id,
        "investor_name": investor_name if holdings else "",
        "holdings": holdings,
    }


def update_portfolio_record(portfolio_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        raise ValueError("At least one field must be provided for update")

    assignments = []
    values: List[Any] = []
    for field, value in payload.items():
        assignments.append(f"{field} = %s")
        values.append(value)
    values.append(portfolio_id)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE user_portfolio SET {', '.join(assignments)} WHERE portfolio_id = %s RETURNING portfolio_id",
                tuple(values),
            )
            updated = cursor.fetchone()
            conn.commit()

    if not updated:
        raise LookupError(f"Portfolio record {portfolio_id} was not found")
    return {"portfolio_id": portfolio_id, "updated": True}


def delete_portfolio_record(portfolio_id: int) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_portfolio WHERE portfolio_id = %s", (portfolio_id,))
            conn.commit()
            return cursor.rowcount > 0


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value
