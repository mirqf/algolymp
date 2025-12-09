import psycopg2, sqlite3
from contextlib import contextmanager

class database:
    def __init__(self):
        self.config = {
            "host": "",
            "database": "postgres",
            "user": "postgres",
            "password": "",
            "port": 5432,
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