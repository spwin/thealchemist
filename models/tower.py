import uuid
# from datetime import datetime
from datetime import datetime

from cassandra.cqlengine import columns
from flask_login._compat import unicode

from models.base import Base


class TowerLocation(Base):
    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    lat = columns.Integer(primary_key=True, partition_key=True)
    lon = columns.Integer(primary_key=True, partition_key=True)

    def __init__(self, lat, lon, **values):
        super().__init__(**values)
        self.lat = lat
        self.lon = lon

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<TowerLocation lat: %r lon: %r>' % (self.lat, self.lat)


class Tower(Base):
    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    location = columns.UUID(primary_key=True, partition_key=True)
    user_id = columns.UUID(primary_key=True)
    created_on = columns.DateTime(default=datetime.utcnow())

    def __init__(self, location, user_id, **values):
        super().__init__(**values)
        self.location = location
        self.user_id = user_id
        self.created_on = datetime.utcnow()

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<Tower id: %r>' % self.id
