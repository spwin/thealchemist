import uuid
from datetime import datetime

from cassandra.cqlengine import columns
from flask_login._compat import unicode
from werkzeug.security import generate_password_hash, check_password_hash

from models.base import Base


class User(Base):
    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    username = columns.Text(index=True)
    email = columns.Text(index=True)
    password = columns.Text()
    lat = columns.Integer()
    lon = columns.Integer()
    current_tower = columns.UUID(index=True)
    registration_data = columns.UUID(primary_key=True)
    registered_on = columns.DateTime(default=datetime.utcnow())

    def __init__(self, username, password, email, registration_data, **values):
        super().__init__(**values)
        self.username = username
        self.set_password(password)
        self.email = email
        self.registration_data = registration_data
        self.registered_on = datetime.utcnow()

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<User %r>' % (self.username)


class UserRegister(Base):
    id = columns.UUID(primary_key=True, default=uuid.uuid4)
    username = columns.Text(primary_key=True, partition_key=True)
    email = columns.Text(primary_key=True, partition_key=True)

    def __init__(self, username, email, **values):
        super().__init__(**values)
        self.username = username
        self.email = email

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<UserRegister %r>' % self.username
