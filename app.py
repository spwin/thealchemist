#!/usr/bin/env python

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
import uuid

from cassandra.cqlengine.query import DoesNotExist, LWTException
import eventlet

eventlet.monkey_patch()

from threading import Thread
from cassandra.cqlengine.models import Model
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
import functools
from flask_login import LoginManager, current_user, login_user, logout_user
from models.user import UserRegister, User
from models.tower import TowerLocation, Tower
from models.resource import Resource, UserFoundResource, ResourceGenerator
from scripts import sync_db
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, message_queue='amqp://', engineio_logger=True)

login_manager = LoginManager()
login_manager.init_app(app)

thread = None
# lon/lat step between two towers
step = 0.01
# towers circles to be sent and bind
circles = 1
# amount of resources near each tower
total_resources_per_tower = 6


##########
# CELERY #
##########
# from celery import Celery
#
#
# def make_celery(app):
#     celery = Celery(app.import_name,
#                     broker=app.config['CELERY_BROKER_URL'])
#     celery.conf.update(app.config)
#     TaskBase = celery.Task
#
#     class ContextTask(TaskBase):
#         abstract = True
#
#         def __call__(self, *args, **kwargs):
#             with app.app_context():
#                 return TaskBase.__call__(self, *args, **kwargs)
#
#     celery.Task = ContextTask
#     return celery


# app.config.update(
#     CELERY_BROKER_URL='amqp://guest:guest@0.0.0.0:5672',
#     CELERY_RESULT_BACKEND='amqp://guest:guest@0.0.0.0:5672'
# )

# celery = make_celery(app)

def create_resource(tower, lat, lon, quantity):
    for i in range(quantity):
        resource = ResourceGenerator(lat, lon)
        resource_db = Resource(type=str(resource.type),
                               lat=resource.lat,
                               lon=resource.lon,
                               quantity=resource.quantity,
                               name=str(resource.name),
                               description=str(resource.description),
                               tower_id=tower)
        resource_db.save()
        message = resource.name + " appeared (lat: " + str(resource.lat / 100000) + ", lon: " + str(
            resource.lon / 100000) + ") quantity: " + str(resource.quantity)
        send_message(resource.name + " appeared")
        socketio.emit('resource_spawned', {'point': {'lat': (resource.lat / 100000), 'lon': (resource.lon / 100000)},
                                           'id': str(resource_db.id),
                                           'towerid': str(tower),
                                           'label': resource.type[0].capitalize(),
                                           'description': resource.description,
                                           'title': resource.name,
                                           'quantity': quantity}, namespace='/main')
        # socketio.emit('resource_spawned', {'msg': message}, namespace='/main', broadcast=True)


@login_manager.user_loader
def load_user(uuid):
    return User.get(id=uuid)


def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            socketio.emit('broadcast',
                          {'msg': 'Not Logged In', 'error': 'auth'},
                          namespace='/main')
            socketio.emit('auth', {'status': 'error', 'action': 'check', 'message': 'You must be logged in'},
                          namespace='/main')
        else:
            return f(*args, **kwargs)

    return wrapped


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        # socketio.emit('chat',
        #               {'msg': 'Server generated event', 'id': 'system', 'count': count},
        #               namespace='/main')


@app.route('/')
def index():
    # global thread
    # if thread is None:
    #     thread = Thread(target=background_thread)
    #     thread.daemon = True
    #     thread.start()
    return render_template('index.html', async_mode=socketio.async_mode)


# @app.route('/advanced')
# def advanced_index():
#     return render_template('advanced.html', async_mode=socketio.async_mode)


@app.route('/points')
def points_index():
    return render_template('points.html', async_mode=socketio.async_mode)


@socketio.on('my_ping', namespace='/main')
def ping_pong(location):
    # if isinstance(location, str):
    #     location = json.loads(location)
    # lat = round(location['lat'] * 100000)
    # lon = round(location['lon'] * 100000)
    # if current_user.is_authenticated:
    #     current_user.update(lat=lat, lon=lon)
    emit('my_pong')


@socketio.on('broadcast', namespace='/main')
def send_message(msg):
    emit('broadcast', {'msg': str(msg)}, broadcast=True)


@socketio.on('bind', namespace='/main')
@authenticated_only
def bind(msg):
    if isinstance(msg, str):
        msg = json.loads(msg)
    for room in rooms()[1:]:
        leave_room(room)
    join_room(msg['tower'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('broadcast',
         {'msg': 'Binded to: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('leave', namespace='/main')
@authenticated_only
def leave(msg):
    leave_room(msg['tower'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('broadcast',
         {'msg': 'Bind to: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('broadcast_tower', namespace='/main')
@authenticated_only
def send_room_message(msg):
    if isinstance(msg, str):
        msg = json.loads(msg)
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('broadcast',
         {'msg': msg['action'], 'count': session['receive_count']},
         room=msg['tower'])


@socketio.on('get_towers', namespace='/main')
@authenticated_only
def get_towers(location):
    if isinstance(location, str):
        location = json.loads(location)
    current_tower = None
    # multiply coordinates by step inverse to store without floating point
    lat = round(location['lat'] * (1 / step))
    lon = round(location['lon'] * (1 / step))

    towers = []
    # leave all current towers
    for room in rooms()[1:]:
        leave_room(room)

    # get or create each tower in circle
    for latitude in range(lat - circles, lat + (circles + 1), 1):
        for longitude in range(lon - circles, lon + (circles + 1), 1):
            # try to find tower in database
            tower = None
            try:
                tower_location = TowerLocation.objects(lat=latitude, lon=longitude).limit(1).get()
            # if tower does not exist, create
            except DoesNotExist as e:
                tower_location = TowerLocation.create(lat=latitude, lon=longitude)
                # create also tower relations table entry
                tower = Tower.create(location=tower_location.id, user_id=current_user.id)
            # join every tower
            join_room(str(tower_location.id))

            # if tower coordinates match current user coordinates, make it current
            if latitude == lat and longitude == lon:
                current_tower = tower_location
            if tower:
                create_resource(tower.id, tower_location.lat, tower_location.lon, total_resources_per_tower)
            # append to towers array to be returned
            towers.append({'lat': tower_location.lat, 'lon': tower_location.lon})
    # if there is current tower, send it to user and update user db info
    if current_tower:
        current_user.update(current_tower=current_tower.id)
        emit('towers_received', {'towers': towers, 'current': {'id': str(current_tower.id),
                                                               'lat': current_tower.lat,
                                                               'lon': current_tower.lon}})
    pass


@socketio.on('register', namespace='/main')
def register_user_call(msg):
    if isinstance(msg, str):
        msg = json.loads(msg)
    try:
        user = UserRegister.objects(username=msg['username'], email=msg['email']).limit(1).get()
        if user:
            emit('auth', {'status': 'error', 'action': 'register', 'message': 'This user already exists'})
    except DoesNotExist as e:
        registration_data = UserRegister.create(username=msg['username'], email=msg['email'])
        user = User.create(username=msg['username'], email=msg['email'],
                           password=msg['password'], registration_data=registration_data.id)
        user.save()
        emit('auth', {'status': 'success', 'action': 'register',
                      'message': 'User ' + user.username + ' (' + user.email + ') has been created'})


@socketio.on('login', namespace='/main')
def login_user_call(msg):
    if isinstance(msg, str):
        msg = json.loads(msg)
    email = msg['email']
    password = msg['password']
    try:
        user = User.get(email=email)
    except DoesNotExist as e:
        user = None

    if user is None or user.check_password(password):
        emit('auth', {'status': 'error', 'action': 'login', 'message': 'Wrong Details'})
    else:
        login_user(user)
        emit('auth',
             {'status': 'success', 'action': 'login', 'message': 'Hi ' + user.username + '! You have been logged in!',
              'user': {
                  'username': user.username,
                  'email': user.email,
                  'lat': user.lat,
                  'lon': user.lon,
                  'current_tower': user.current_tower
              }})


@socketio.on('logout', namespace='/main')
@authenticated_only
def logout_user_call(location):
    logout_user()
    emit('broadcast', {'msg': 'You have been logged out'})


@socketio.on('get_points', namespace='/main')
def get_points(location):
    if isinstance(location, str):
        location = json.loads(location)

    lat = round(location['lat'] * (1 / step))
    lon = round(location['lon'] * (1 / step))

    points = []
    towers = []
    tower_locations = []

    for latitude in range(lat - circles, lat + (circles + 1), 1):
        for longitude in range(lon - circles, lon + (circles + 1), 1):
            try:
                tower_location = TowerLocation.objects(lat=latitude, lon=longitude).limit(1).get()
                tower_locations.append(tower_location.id)
            except DoesNotExist as e:
                print(e)

    for tower in Tower.objects(location__in=tower_locations):
        towers.append(tower)
    try:
        for point in Resource.objects(tower_id__in=list(tower.id for tower in towers)):
            points.append({'location': {'lat': point.lat / 100000, 'lon': point.lon / 100000},
                           'id': point.get_id(),
                           'towerid': str(point.tower_id),
                           'label': point.type[0].capitalize(),
                           'description': point.description,
                           'quantity': point.quantity,
                           'title': point.name})
    except DoesNotExist as e:
        print(e)
    emit('receive_points', {'points': points})


@socketio.on('resource_found', namespace='/main')
# @authenticated_only
def resource_found(point):
    print(point)
    if isinstance(point, str):
        point = json.loads(point)
    idx = uuid.UUID(point['id'])
    tower_id = uuid.UUID(point['tower_id'])
    resource = None
    try:
        resource = Resource.get(tower_id=tower_id, id=idx)
    except DoesNotExist as e:
        print(e)
    if resource:
        print(resource)
        if not current_user.is_authenticated:
            user_id = uuid.UUID('5da5957c-9775-4f5f-b257-4a93a520b15c')
        else:
            user_id = current_user.id
        user_resource = UserFoundResource(id=resource.id,
                                          user_id=user_id,
                                          type=resource.type,
                                          lat=resource.lat,
                                          lon=resource.lon,
                                          quantity=resource.quantity,
                                          name=resource.name,
                                          description=resource.description,
                                          tower_id=resource.tower_id)
        user_resource.save()
        resource.delete()
        towerLocation = TowerLocation.get(lat=round(resource.lat / 1000), lon=round(resource.lon / 1000))
        create_resource(str(tower_id), towerLocation.lat, towerLocation.lon, 1)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=False)
