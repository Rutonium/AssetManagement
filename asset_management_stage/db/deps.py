from collections.abc import Generator

from .session import SessionLocalAsset, SessionLocalTimeApp


def get_asset_db() -> Generator:
    db = SessionLocalAsset()
    try:
        yield db
    finally:
        db.close()


def get_timeapp_db() -> Generator:
    db = SessionLocalTimeApp()
    try:
        yield db
    finally:
        db.close()
