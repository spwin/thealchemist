from cassandra.cqlengine import connection
from cassandra.cqlengine.management import sync_table
from models.user import UserRegister, User
from models.tower import Tower, TowerLocation
from models.resource import Resource
import os

os.environ["CQLENG_ALLOW_SCHEMA_MANAGEMENT"] = 'CQLENG_ALLOW_SCHEMA_MANAGEMENT'

connection.setup(['127.0.0.1'], "cqlengine", protocol_version=3)

sync_table(User)
sync_table(UserRegister)
sync_table(Tower)
sync_table(TowerLocation)
sync_table(Resource)
