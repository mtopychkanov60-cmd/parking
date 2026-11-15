import pytest

from models import Client, Parking, ClientParking
from factories import ClientFactory, ParkingFactory

CLIENT_ID = 1
PARKING_ID = 1
BODY = {"client_id": CLIENT_ID, "parking_id": PARKING_ID}


def get_parking(db, parking_id=PARKING_ID):
    db.session.expire_all()
    return db.session.get(Parking, parking_id)


def get_log(db, client_id=CLIENT_ID, parking_id=PARKING_ID):
    db.session.expire_all()
    return db.session.execute(
        db.select(ClientParking).filter_by(client_id=client_id, parking_id=parking_id)
    ).scalar_one()


def add_client(db, **kwargs):
    c = Client(**{"name": "Анна", "surname": "Сидорова", **kwargs})
    db.session.add(c)
    db.session.commit()
    return c


def add_parking(db, **kwargs):
    p = Parking(
        **{
            "address": "пр. Мира, 5",
            "opened": True,
            "count_places": 5,
            "count_available_places": 5,
            **kwargs,
        }
    )
    db.session.add(p)
    db.session.commit()
    return p


def count_rows(db, model):
    db.session.expire_all()
    return db.session.scalar(db.select(db.func.count()).select_from(model))


def test_create_client_with_factory(client, db):
    clients_before = count_rows(db, Client)
    data = ClientFactory.build()  # объект в памяти, в БД не пишется

    payload = {
        "name": data.name,
        "surname": data.surname,
        "credit_card": data.credit_card,
        "car_number": data.car_number,
    }
    response = client.post("/clients", json=payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] is not None
    assert count_rows(db, Client) == clients_before + 1

    created = db.session.get(Client, body["id"])
    assert created.name == data.name
    assert created.surname == data.surname
    assert created.credit_card == data.credit_card
    assert created.car_number == data.car_number


def test_create_parking_with_factory(client, db):
    parkings_before = count_rows(db, Parking)
    data = ParkingFactory.build()

    payload = {
        "address": data.address,
        "opened": data.opened,
        "count_places": data.count_places,
    }
    response = client.post("/parkings", json=payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] is not None
    assert count_rows(db, Parking) == parkings_before + 1

    created = db.session.get(Parking, body["id"])
    assert created.address == data.address
    assert created.opened == data.opened
    assert created.count_places == data.count_places
    assert created.count_available_places == data.count_places


@pytest.mark.parametrize("url", ["/clients", f"/clients/{CLIENT_ID}"])
def test_get_methods_return_200(client, url):
    response = client.get(url)
    assert response.status_code == 200


def test_get_unknown_client_returns_404(client):
    assert client.get("/clients/999").status_code == 404


def test_get_clients_returns_list(client):
    data = client.get("/clients").get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Иван"


def test_create_client(client, db):
    payload = {
        "name": "Мария",
        "surname": "Иванова",
        "credit_card": "5555555555554444",
        "car_number": "В777ОР36",
    }
    response = client.post("/clients", json=payload)

    assert response.status_code == 201
    new_id = response.get_json()["id"]
    created = db.session.get(Client, new_id)
    assert created.name == "Мария"
    assert created.car_number == "В777ОР36"


def test_create_client_without_required_fields(client):
    response = client.post("/clients", json={"name": "Мария"})
    assert response.status_code == 400


def test_create_parking(client, db):
    payload = {"address": "ул. Кирова, 10", "count_places": 20, "opened": True}
    response = client.post("/parkings", json=payload)

    assert response.status_code == 201
    created = db.session.get(Parking, response.get_json()["id"])
    assert created.address == "ул. Кирова, 10"
    assert created.count_places == 20
    # при создании все места свободны
    assert created.count_available_places == 20


def test_create_parking_with_invalid_places(client):
    response = client.post("/parkings", json={"address": "ул. Кирова", "count_places": 0})
    assert response.status_code == 400


@pytest.mark.parking
def test_enter_parking(client, db):
    before = get_parking(db).count_available_places

    response = client.post("/client_parkings", json=BODY)

    assert response.status_code == 201
    assert get_parking(db).count_available_places == before - 1
    log = get_log(db)
    assert log.time_in is not None
    assert log.time_out is None


@pytest.mark.parking
def test_enter_closed_parking(client, db):
    closed = add_parking(db, opened=False)

    response = client.post(
        "/client_parkings", json={"client_id": CLIENT_ID, "parking_id": closed.id}
    )

    assert response.status_code == 400
    assert get_parking(db, closed.id).count_available_places == 5


@pytest.mark.parking
def test_enter_parking_without_free_places(client, db):
    full = add_parking(db, count_places=1, count_available_places=0)

    response = client.post("/client_parkings", json={"client_id": CLIENT_ID, "parking_id": full.id})

    assert response.status_code == 400
    assert get_parking(db, full.id).count_available_places == 0


@pytest.mark.parking
def test_enter_parking_twice(client, db):
    client.post("/client_parkings", json=BODY)
    places_after_first = get_parking(db).count_available_places

    response = client.post("/client_parkings", json=BODY)

    assert response.status_code == 400
    assert get_parking(db).count_available_places == places_after_first


@pytest.mark.parking
def test_enter_unknown_client_or_parking(client):
    assert (
        client.post(
            "/client_parkings", json={"client_id": 999, "parking_id": PARKING_ID}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/client_parkings", json={"client_id": CLIENT_ID, "parking_id": 999}
        ).status_code
        == 404
    )


@pytest.mark.parking
def test_leave_parking(client, db):
    client.post("/client_parkings", json=BODY)
    places_after_enter = get_parking(db).count_available_places

    response = client.delete("/client_parkings", json=BODY)

    assert response.status_code == 200
    assert get_parking(db).count_available_places == places_after_enter + 1

    log = get_log(db)
    assert log.time_out is not None
    assert log.time_out >= log.time_in
    assert response.get_json()["amount"] > 0


@pytest.mark.parking
def test_leave_parking_without_card(client, db):
    no_card = add_client(db, credit_card=None)
    body = {"client_id": no_card.id, "parking_id": PARKING_ID}
    client.post("/client_parkings", json=body)
    places_after_enter = get_parking(db).count_available_places

    response = client.delete("/client_parkings", json=body)

    assert response.status_code == 400
    assert get_parking(db).count_available_places == places_after_enter
    assert get_log(db, client_id=no_card.id).time_out is None


@pytest.mark.parking
def test_leave_parking_if_not_parked(client, db):
    before = get_parking(db).count_available_places

    response = client.delete("/client_parkings", json=BODY)

    assert response.status_code == 400
    assert get_parking(db).count_available_places == before


@pytest.mark.parking
def test_reenter_after_leaving(client, db):
    client.post("/client_parkings", json=BODY)
    client.delete("/client_parkings", json=BODY)

    response = client.post("/client_parkings", json=BODY)

    assert response.status_code == 201
    assert get_log(db).time_out is None
