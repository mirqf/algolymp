import psycopg2, sqlite3, os, datetime
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

class database:
    def __init__(self):
        self.config = {
            "host": os.getenv("DB_HOST", "147.45.102.219"),
            "database": os.getenv("DB_DATABASE", "postgres"),
            "user": os.getenv("BOT_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "genatasks777"),
            "port": int(os.getenv("DB_PORT", 5432)),
        }
        self.connection = None
    
    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.config)
            return self.connection
        except psycopg2.Error as exp:
            return None
    
    def disconnect(self):
        if self.connection:
            self.connection.close()
    
    @contextmanager
    def get_cursor(self):
        if not self.connection or self.connection.closed:
            self.connect()
        if self.connection is None:
            raise RuntimeError("Database connection failed (check DB_HOST, DB_DATABASE, BOT_USER, DB_PASSWORD, DB_PORT)")
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except:
            self.connection.rollback()
            raise
        finally:
            cursor.close()
            self.disconnect()

    def get_all_events_table(self) -> list:
        """Возвращает все мероприятия из events в виде списка словарей (id, name, description)."""
        with self.get_cursor() as cur:
            cur.execute("SELECT id, name, description FROM events ORDER BY name")
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    
    def delete_event_by_id(self, event_id) -> bool:
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM event_blocks WHERE event_id = %s", (event_id,))
            cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
        
    def create_event_by_raw(self, data: dict) -> bool:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM events")
            event_id = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM event_blocks")
            block_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO events (id, name, description)
                VALUES (%s, %s, %s)
            """, (event_id, data.get("name", "Unknown Name"), data.get("description", ""))) 

            for idx, tour_data in enumerate(data.get("tours", list())):
                cursor.execute("""
                    INSERT INTO event_blocks (id, event_id, start_date, end_date, name, description, link)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (block_id + idx, event_id, tour_data.get("start_date", datetime.now()), tour_data.get("end_date", datetime.now()), tour_data.get("tour_name", "Unknown Tour"), '', data.get("description", '')))

        return True

    def update_event_by_raw(self, event_id, data: dict) -> bool:
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                    UPDATE events
                    SET name = %s, description = %s
                    WHERE id = %s
                """,
                (data.get("name", "Unknown Name"), data.get("description", ""), event_id)
            )

            cursor.execute("DELETE FROM event_blocks WHERE event_id = %s", (event_id,))

            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM event_blocks")
            block_id = cursor.fetchone()[0]

            for idx, tour_data in enumerate(data.get("tours", list())):
                cursor.execute(
                    """
                        INSERT INTO event_blocks (id, event_id, start_date, end_date, name, description, link)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        block_id + idx,
                        event_id,
                        tour_data.get("start_date", datetime.now()),
                        tour_data.get("end_date", datetime.now()),
                        tour_data.get("tour_name", "Unknown Tour"),
                        '',
                        data.get("description", '')
                    )
                )

        return True

    def copy_to_sqlite(self, sqlite_path: str = "dump.sql"):
        sq_conn = sqlite3.connect(sqlite_path)
        sq_cur = sq_conn.cursor()

        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                tables = [r[0] for r in cur.fetchall()]

                for table in tables:
                    cur.execute(f"SELECT * FROM {table} LIMIT 0")
                    col_names = [desc.name for desc in cur.description]
                    col_types_pg = [desc.type_code for desc in cur.description]

                    col_types_sqlite = []
                    for t in col_types_pg:
                        if t in (23, 20, 21):          # int4, int8, int2
                            col_types_sqlite.append("INTEGER")
                        elif t in (700, 701, 1700):   # float4, float8, numeric
                            col_types_sqlite.append("REAL")
                        elif t in (17,):              # bytea
                            col_types_sqlite.append("BLOB")
                        else:
                            col_types_sqlite.append("TEXT")

                    cols_def = ", ".join(
                        f'"{n}" {t}' for n, t in zip(col_names, col_types_sqlite)
                    )

                    sq_cur.execute(f'DROP TABLE IF EXISTS "{table}"')
                    sq_cur.execute(f'CREATE TABLE "{table}" ({cols_def})')

                    cur.execute(f'SELECT * FROM "{table}"')
                    while True:
                        rows = cur.fetchmany(1000)
                        if not rows:
                            break
                        placeholders = ", ".join(["?"] * len(col_names))
                        sq_cur.executemany(
                            f'INSERT INTO "{table}" VALUES ({placeholders})',
                            rows,
                        )

            sq_conn.commit()
        finally:
            sq_cur.close()
            sq_conn.close()

if __name__ == "__main__":
    d = database()
    d.copy_to_sqlite()
