import os
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app


# GitHub Actions will provide TEST_DATABASE_URL.
# Locally, this falls back to your local test database.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:0707@localhost:5432/expenseiq_test_db"
)


test_engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


# Override FastAPI database dependency during testing
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():

    # Create clean test database tables
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    # Clean up after all tests
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client