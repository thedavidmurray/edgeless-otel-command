#!/usr/bin/env python3
"""Apply RLHF schema to the job search database."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from streamlit_app.common import DB_PATH


def apply_rlhf_schema():
    """Apply the RLHF schema to the database."""

    schema_file = Path(__file__).parent / "db" / "rlhf_schema.sql"

    if not schema_file.exists():
        print(f"Schema file not found: {schema_file}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)

        with open(schema_file, "r") as f:
            schema_sql = f.read()

        # Execute the schema
        conn.executescript(schema_sql)
        conn.commit()

        print("RLHF schema applied successfully!")

        # Verify tables were created
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'rlhf_%' OR name LIKE '%_tracking' OR name LIKE '%_outcomes' OR name LIKE '%_patterns'
        """
        )

        tables = cursor.fetchall()
        print(f"Created tables: {[t[0] for t in tables]}")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    apply_rlhf_schema()
