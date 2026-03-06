"""Rebuild all v2 experience projection tables from raw source-of-truth tables."""

from app.db.session import SessionLocal
from app.services.experience_projection import rebuild_experience_projection_all


def main() -> None:
    with SessionLocal() as db:
        rebuild_experience_projection_all(db)
        db.commit()
    print("Experience projection rebuild complete.")


if __name__ == "__main__":
    main()
