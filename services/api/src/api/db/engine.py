from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from services.api.src.api.config import settings


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    return create_engine(url, echo=False)


def init_db(engine: Engine) -> None:
    from services.api.src.api.db.models import metadata

    metadata.create_all(engine)
