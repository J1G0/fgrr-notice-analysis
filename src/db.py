import os
import psycopg2

TABLE_NAME = "fgrr_notices"

BASE_COLUMNS = {
    "번호": "TEXT",
    "파일명": "TEXT",
    "지방산림청": "TEXT",
    "고시번호": "TEXT",
    "유형": "TEXT",
    "고시날짜": "TEXT",
    "유전자원보호구역_여부": "BOOLEAN",
    "소재지": "TEXT",
    "지번": "TEXT",
    "임반": "TEXT",
    "지목": "TEXT",
    "소유자": "TEXT",
    "지적": "TEXT",
    "지정면적": "TEXT",
    "해제면적": "TEXT",
    "잔여면적": "TEXT",
    "지정유형": "TEXT",
    "해제사유": "TEXT",
    "명칭": "TEXT",
    "비고": "TEXT",
    "raw_text": "TEXT",
}


class DB:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.known_columns: set[str] = set()
        self._init_table()

    def _init_table(self):
        with self.conn.cursor() as cur:
            cols_def = ",\n    ".join(
                f'"{col}" {dtype}' for col, dtype in BASE_COLUMNS.items()
            )
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id SERIAL PRIMARY KEY,
                    {cols_def}
                )
            """)
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                """,
                (TABLE_NAME,),
            )
            self.known_columns = {row[0] for row in cur.fetchall()}
        self.conn.commit()

    def ensure_column(self, col: str):
        if col in self.known_columns:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                f'ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS "{col}" TEXT'
            )
        self.conn.commit()
        self.known_columns.add(col)
        print(f"  [DB] 새 컬럼 추가: {col}")

    def insert_rows(self, rows: list[dict]):
        if not rows:
            return
        for col in {k for row in rows for k in row}:
            self.ensure_column(col)

        try:
            with self.conn.cursor() as cur:
                for row in rows:
                    cols = list(row.keys())
                    vals = [row[c] for c in cols]
                    col_sql = ", ".join(f'"{c}"' for c in cols)
                    placeholders = ", ".join(["%s"] * len(cols))
                    cur.execute(
                        f"INSERT INTO {TABLE_NAME} ({col_sql}) VALUES ({placeholders})",
                        vals,
                    )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def already_processed(self, filename: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                f'SELECT 1 FROM {TABLE_NAME} WHERE "파일명" = %s LIMIT 1',
                (filename,),
            )
            return cur.fetchone() is not None

    def close(self):
        self.conn.close()
