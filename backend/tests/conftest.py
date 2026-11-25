from __future__ import annotations

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["APP_ENV"] = "development"

from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add_all(
            [
                User(
                    username=username,
                    display_name=username,
                    password_hash=hash_password("Demo123!"),
                    role=role,
                )
                for username, role in [
                    ("user001", Role.USER),
                    ("user002", Role.USER),
                    ("agent001", Role.AGENT),
                    ("agent002", Role.AGENT),
                    ("admin", Role.ADMIN),
                ]
            ]
        )
        db.commit()
    with TestClient(app) as test_client:
        yield test_client

