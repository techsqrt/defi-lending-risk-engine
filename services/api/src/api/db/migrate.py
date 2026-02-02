"""Run database migrations on startup."""

from pathlib import Path

from sqlalchemy import text

from services.api.src.api.db.engine import get_engine


def run_migrations() -> None:
    """Execute all SQL migration files in order."""
    migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"

    if not migrations_dir.exists():
        print(f"Migrations directory not found: {migrations_dir}")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found")
        return

    engine = get_engine()

    with engine.connect() as conn:
        for migration_file in migration_files:
            print(f"Running migration: {migration_file.name}")
            sql = migration_file.read_text()

            # Split by semicolon and execute each statement
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        # Ignore "already exists" errors
                        if "already exists" in str(e).lower():
                            pass
                        else:
                            print(f"  Warning: {e}")

            conn.commit()
            print(f"  Done: {migration_file.name}")

    print("All migrations complete")


if __name__ == "__main__":
    run_migrations()
