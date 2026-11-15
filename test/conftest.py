from datetime import datetime, timedelta

import pytest

from app import create_app
from models import db as _db, Client, Parking, ClientParking


@pytest.fixture
def app():
    _app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with _app.app_context():
        _db.create_all()

        client = Client(
            name="Иван",
            surname="Петров",
            credit_card="4111111111111111",
            car_number="А123ВС36",
        )
        parking = Parking(
            address="ул. Ленина, 1",
            opened=True,
            count_places=10,
            count_available_places=10,
        )
        _db.session.add_all([client, parking])
        _db.session.commit()

        now = datetime.now()
        log = ClientParking(
            client_id=client.id,
            parking_id=parking.id,
            time_in=now - timedelta(hours=2),
            time_out=now - timedelta(hours=1),
        )
        _db.session.add(log)
        _db.session.commit()

        yield _app

        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db