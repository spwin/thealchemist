import uuid
from datetime import datetime
from cassandra.cqlengine import columns
from flask_login._compat import unicode
from models.base import Base
from numpy.random import choice
import random
import math


class Resource(Base):
    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    type = columns.Text(primary_key=True)
    lat = columns.Integer(primary_key=True)
    lon = columns.Integer(primary_key=True)
    quantity = columns.Integer()
    name = columns.Text()
    description = columns.Text()
    tower_id = columns.UUID(primary_key=True, partition_key=True)

    def __init__(self, type, lat, lon, quantity, name, description, tower_id, **values):
        super().__init__(**values)
        self.type = type
        self.lat = lat
        self.lon = lon
        self.quantity = quantity
        self.name = name
        self.description = description
        self.tower_id = tower_id

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<Resource type: %r lat: %r lon: %r>' % (self.type, self.lat, self.lon)


class UserFoundResource(Base):
    id = columns.UUID(primary_key=True)
    user_id = columns.UUID(primary_key=True, partition_key=True)
    type = columns.Text(primary_key=True)
    lat = columns.Integer(primary_key=True)
    lon = columns.Integer(primary_key=True)
    quantity = columns.Integer()
    name = columns.Text()
    description = columns.Text()

    def __init__(self, id, user_id, type, lat, lon, quantity, name, description, tower_id, **values):
        super().__init__(**values)
        self.id = id
        self.user_id = user_id
        self.type = type
        self.lat = lat
        self.lon = lon
        self.quantity = quantity
        self.name = name
        self.description = description
        self.tower_id = tower_id

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<FoundResource type: %r lat: %r lon: %r user_id: %r>' % (self.type, self.lat, self.lon, str(self.user_id))


class ResourceGenerator:
    resources = {
        'lead': 20,
        'tin': 15,
        'silver': 10,
        'gold': 5,
        'mercury': 15,
        'iron': 20,
        'sulfur': 15,
        'manuscript': 1
    }
    names = {
        'lead': 'Lead',
        'tin': 'Tin',
        'silver': 'Silver',
        'gold': 'Gold',
        'mercury': 'Mercury',
        'iron': 'Iron',
        'sulfur': 'Sulfur',
        'manuscript': 'Manuscript'
    }
    descriptions = {
        'lead': 'Svinec',
        'tin': 'Olovo',
        'silver': 'Serebro',
        'gold': 'Zoloto',
        'mercury': 'Rtut',
        'iron': 'Zhelezo',
        'sulfur': 'Sera',
        'manuscript': 'Manuskript'
    }
    lat = None
    lon = None
    quantity = None
    type = None
    name = None
    description = None
    step = 0.01
    coordinates_decimals = 5

    def __init__(self, lat, lon):
        frequencies = {key: float(value) / sum(self.resources.values()) for (key, value) in self.resources.items()}
        self.type = choice(list(frequencies.keys()), p=list(frequencies.values()))

        # store as integer with 5 decimals
        self.lat = math.ceil(
            ((lat * self.step - self.step / 2) + random.random() * self.step) * (10 ** self.coordinates_decimals))
        self.lon = math.ceil(
            ((lon * self.step - self.step / 2) + random.random() * self.step) * (10 ** self.coordinates_decimals))

        self.quantity = math.ceil(random.random() * self.resources[self.type])
        self.name = self.names[self.type]
        self.description = self.descriptions[self.type]

    def __repr__(self):
        return '<GeneratedResource type: %r lat: %r lon: %r>' % (self.type, self.lat, self.lon)
