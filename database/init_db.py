import sqlite3
from pathlib import Path


# Get the database directory
BASE_DIR = Path(__file__).resolve().parent

# Define file paths
SCHEMA_FILE = BASE_DIR / "schema.sql"
DATABASE_FILE = BASE_DIR / "multyvers.db"


def initialize_database():

    # Check whether schema exists
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError("Database schema not found!")

    # Connect to SQLite database
    connection = sqlite3.connect(DATABASE_FILE)

    try:
        # Enable foreign key constraints
        connection.execute("PRAGMA foreign_keys = ON")

        # Read SQL schema
        schema = SCHEMA_FILE.read_text(encoding="utf-8")

        # Execute all SQL commands
        connection.executescript(schema)

        # Save changes
        connection.commit()

        print("MULTYVERS database initialized successfully!")

        # Verify created tables
        cursor = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)

        tables = cursor.fetchall()

        print("\nTables created:")

        for table in tables:
            print(f"- {table[0]}")

        print(f"\nDatabase location: {DATABASE_FILE}")

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()