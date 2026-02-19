import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


ASSET_MANAGEMENT_DB_URL = _require_env("ASSET_MANAGEMENT_DB_URL")
TIMEAPP_DB_URL = _require_env("TIMEAPP_DB_URL")

engine_asset = create_engine(
    ASSET_MANAGEMENT_DB_URL,
    pool_pre_ping=True,
    future=True,
)

engine_timeapp = create_engine(
    TIMEAPP_DB_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocalAsset = sessionmaker(
    bind=engine_asset,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

SessionLocalTimeApp = sessionmaker(
    bind=engine_timeapp,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
