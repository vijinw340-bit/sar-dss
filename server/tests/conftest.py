"""Pytest fixtures and environment for SAR-DSS tests (SQLite backend)."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_sar_dss.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "Admin@123"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Create schema and a bootstrap admin before all tests run."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    email="admin@test.aai.in",
                    full_name="Test Admin",
                    role="admin",
                    hashed_password=hash_password("Admin@123"),
                )
            )
            db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
