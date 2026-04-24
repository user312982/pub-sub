import tempfile
import os

import pytest
from fastapi.testclient import TestClient

from src.dedup_store import DedupStore
from src.stats import Stats
from src.main import create_app


@pytest.fixture
def dedup_store():
    tmp = tempfile.mktemp(suffix=".db")
    store = DedupStore(tmp)
    yield store
    store.close()
    os.unlink(tmp)


@pytest.fixture
def stats():
    return Stats()


@pytest.fixture
def app(dedup_store, stats):
    return create_app(dedup_store=dedup_store, stats=stats)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
