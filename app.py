from datetime import datetime

from flask import Flask, jsonify, request

from models import db, Client, Parking, ClientParking

PRICE_PER_HOUR = 100


def create_app(config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parking.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if config:
        app.config.update(config)

    db.init_app(app)

    with app.app_context():
        db.create_all()


    @app.route("/clients", methods=["GET"])
    def get_clients():
        clients = db.session.execute(db.select(Client)).scalars().all()
        return jsonify([c.to_json() for c in clients]), 200

    @app.route("/clients/<int:client_id>", methods=["GET"])
    def get_client(client_id):
        client = db.session.get(Client, client_id)
        if client is None:
            return jsonify({"error": "Клиент не найден"}), 404
        return jsonify(client.to_json()), 200

    @app.route("/clients", methods=["POST"])
    def create_client():
        data = request.get_json(silent=True) or {}
        name, surname = data.get("name"), data.get("surname")
        if not name or not surname:
            return jsonify({"error": "Поля name и surname обязательны"}), 400

        client = Client(
            name=name,
            surname=surname,
            credit_card=data.get("credit_card"),
            car_number=data.get("car_number"),
        )
        db.session.add(client)
        db.session.commit()
        return jsonify(client.to_json()), 201

    @app.route("/parkings", methods=["POST"])
    def create_parking():
        data = request.get_json(silent=True) or {}
        address, count_places = data.get("address"), data.get("count_places")
        if not address or not isinstance(count_places, int) or count_places <= 0:
            return jsonify(
                {"error": "Нужны address и положительное целое count_places"}
            ), 400

        parking = Parking(
            address=address,
            opened=data.get("opened", True),
            count_places=count_places,
            count_available_places=count_places,
        )
        db.session.add(parking)
        db.session.commit()
        return jsonify(parking.to_json()), 201


    def _get_client_and_parking(data):
        client_id, parking_id = data.get("client_id"), data.get("parking_id")
        if client_id is None or parking_id is None:
            return None, None, (
                jsonify({"error": "Нужны client_id и parking_id"}), 400
            )
        client = db.session.get(Client, client_id)
        parking = db.session.get(Parking, parking_id)
        if client is None:
            return None, None, (jsonify({"error": "Клиент не найден"}), 404)
        if parking is None:
            return None, None, (jsonify({"error": "Парковка не найдена"}), 404)
        return client, parking, None

    def _find_log(client_id, parking_id):
        return db.session.execute(
            db.select(ClientParking).filter_by(
                client_id=client_id, parking_id=parking_id
            )
        ).scalar_one_or_none()

    @app.route("/client_parkings", methods=["POST"])
    def enter_parking():
        data = request.get_json(silent=True) or {}
        client, parking, error = _get_client_and_parking(data)
        if error:
            return error

        if not parking.opened:
            return jsonify({"error": "Парковка закрыта"}), 400
        if parking.count_available_places <= 0:
            return jsonify({"error": "Нет свободных мест"}), 400

        log = _find_log(client.id, parking.id)
        if log is not None and log.time_out is None:
            return jsonify({"error": "Клиент уже находится на этой парковке"}), 400

        if log is None:
            log = ClientParking(client_id=client.id, parking_id=parking.id)
            db.session.add(log)
        log.time_in = datetime.now()
        log.time_out = None

        parking.count_available_places -= 1
        db.session.commit()
        return jsonify(log.to_json()), 201

    @app.route("/client_parkings", methods=["DELETE"])
    def leave_parking():
        data = request.get_json(silent=True) or {}
        client, parking, error = _get_client_and_parking(data)
        if error:
            return error

        log = _find_log(client.id, parking.id)
        if log is None or log.time_out is not None:
            return jsonify({"error": "Клиент не находится на этой парковке"}), 400

        if not client.credit_card:
            return jsonify(
                {"error": "У клиента не привязана карта, оплата невозможна"}
            ), 400

        log.time_out = datetime.now()
        hours = (log.time_out - log.time_in).total_seconds() / 3600
        amount = round(max(hours, 1) * PRICE_PER_HOUR, 2)  # минимум 1 час

        parking.count_available_places += 1
        db.session.commit()
        return jsonify({**log.to_json(), "amount": amount}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)