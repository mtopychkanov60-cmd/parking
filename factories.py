import random

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker

from models import db, Client, Parking

fake = Faker()


def maybe_credit_card():
    return fake.credit_card_number() if random.choice([True, False]) else None


class ClientFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Client
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"

    name = factory.Faker("first_name")
    surname = factory.Faker("last_name")
    credit_card = factory.LazyFunction(maybe_credit_card)
    car_number = factory.Faker("pystr", max_chars=10)


class ParkingFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Parking
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"

    address = factory.Faker("address")
    opened = factory.Faker("pybool")
    count_places = factory.Faker("random_int", min=10, max=100)
    count_available_places = factory.LazyAttribute(lambda obj: obj.count_places)
