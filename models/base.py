from cassandra.cqlengine.models import Model


class Base(Model):
    __abstract__ = True
    __keyspace__ = "the_alchemist"
