import os
import sqlite3
import logging
import time
from pathlib import Path
from datetime import date

logger = logging.getLogger("db_service")

# Try importing psycopg2 for PostgreSQL support
try:
    import psycopg2
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

# Database path for SQLite fallback
DB_DIR = Path(__file__).resolve().parent.parent / "data"
SQLITE_PATH = DB_DIR / "local_portfolio.db"

# Cached failure timestamp to prevent repeated timeout lag
_POSTGRES_FAILED_UNTIL = 0.0
POSTGRES_COOLDOWN_SECONDS = 120.0  # Don't try RDS for 2 minutes after a timeout

class SQLiteCursorAdapter:
    def __init__(self, sqlite_cursor):
        self.cursor = sqlite_cursor

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        if params:
            self.cursor.execute(sql, params)
        else:
            self.cursor.execute(sql)

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    def close(self):
        self.cursor.close()

class SQLiteConnectionAdapter:
    def __init__(self, sqlite_conn):
        self.conn = sqlite_conn

    def cursor(self):
        return SQLiteCursorAdapter(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

def get_db_connection():
    """Attempt to connect to PostgreSQL RDS database, falling back to local SQLite if it fails."""
    global _POSTGRES_FAILED_UNTIL
    
    host = os.getenv("DB_HOST", "prasuk-practice-db.cpckkgcwoy32.ap-south-1.rds.amazonaws.com")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "postgres")
    user = os.getenv("DB_USER", "pgadmin")
    password = os.getenv("DB_PASSWORD", "YourOwnStrongPassword123!")

    current_time = time.time()
    
    # Check if we should attempt PostgreSQL or bypass it due to cached failure
    if HAS_POSTGRES and host and current_time > _POSTGRES_FAILED_UNTIL:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=3
            )
            logger.info("Successfully connected to AWS RDS PostgreSQL.")
            return conn
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL RDS: {e}. Falling back to SQLite.")
            _POSTGRES_FAILED_UNTIL = current_time + POSTGRES_COOLDOWN_SECONDS
            
    # SQLite Fallback
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
    return SQLiteConnectionAdapter(conn)

def init_db():
    """Create the necessary database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    is_sqlite = isinstance(conn, SQLiteConnectionAdapter)
    
    if is_sqlite:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS user_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            units REAL NOT NULL,
            purchase_date TEXT NOT NULL,
            purchase_price REAL NOT NULL
        )
        """
    else:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS user_portfolio (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            asset_type VARCHAR(20) NOT NULL,
            symbol VARCHAR(100) NOT NULL,
            units NUMERIC NOT NULL,
            purchase_date DATE NOT NULL,
            purchase_price NUMERIC NOT NULL
        )
        """
        
    try:
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("user_portfolio table initialized.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}")
    finally:
        cursor.close()
        conn.close()

def add_holding(user_id: str, asset_type: str, symbol: str, units: float, purchase_date: str, purchase_price: float):
    """Add a holding to the user's portfolio."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
    INSERT INTO user_portfolio (user_id, asset_type, symbol, units, purchase_date, purchase_price)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(sql, (user_id, asset_type, symbol, units, purchase_date, purchase_price))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding holding: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

def get_holdings(user_id: str):
    """Retrieve all holdings for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
    SELECT id, user_id, asset_type, symbol, units, purchase_date, purchase_price
    FROM user_portfolio
    WHERE user_id = %s
    """
    try:
        cursor.execute(sql, (user_id,))
        rows = cursor.fetchall()
        holdings = []
        for r in rows:
            pdate = r[5]
            if isinstance(pdate, (date,)):
                pdate = pdate.isoformat()
            holdings.append({
                "id": r[0],
                "user_id": r[1],
                "asset_type": r[2],
                "symbol": r[3],
                "units": float(r[4]),
                "purchase_date": str(pdate),
                "purchase_price": float(r[6])
            })
        return holdings
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def delete_holding(holding_id: int):
    """Delete a holding by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM user_portfolio WHERE id = %s"
    try:
        cursor.execute(sql, (holding_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting holding: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
