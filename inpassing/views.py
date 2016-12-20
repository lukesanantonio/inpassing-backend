# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import request, jsonify

from . import pass_util
from .app import app
from .models import Org, User, Pass, db

from .util import jwt_optional, range_inclusive_dates

import datetime
import json
import bcrypt

from flask_jwt_extended import JWTManager, jwt_required, create_access_token,\
    create_refresh_token, jwt_refresh_token_required, get_jwt_identity

from datetime import timedelta, datetime

from .worker import DATE_FMT

import redis
from .worker.queue import LiveObj, LiveOrg

jwt = JWTManager(app)

redis = redis.StrictRedis(host='localhost', port=6379, db=0)
live_orgs = {}

@jwt.user_identity_loader
def user_identity(ident):
    # The user is identified with their ID.
    return ident.id

@app.route('/user/signup', methods=['POST'])
def user_signup():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    password = request.form.get('password')

    err = None
    if first_name is None:
        err = {
            'field_missing': 'first_name',
            'msg': 'first name is a required field'
        }
    elif last_name is None:
        err = {
            'field_missing': 'last_name',
            'msg': 'last name is a required field'
        }
    elif email is None:
        err = {
            'field_missing': 'email',
            'msg': 'email is a required field'
        }
    elif password is None:
        err = {
            'field_missing': 'password',
            'msg': 'password is a required field'
        }

    if err != None:
        return jsonify(err), 422

    # Hash password, add user, return response.
    hashpass = bcrypt.hashpw(password, bcrypt.gensalt(12))
    user = User(first_name=first_name, last_name=last_name, email=email,
                password=hashpass)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'user_id': user.id,
        'msg': 'successfully created new user'
    }), 200

# Idea: Add anonymous auth @ GET /auth/anon.jwt or something
@app.route('/user/auth', methods=['POST'])
def auth_user():
    in_email = request.form.get('email', '')
    in_passwd = request.form.get('password', '')

    user = db.session.query(User).filter_by(email=in_email).first()

    if user and bcrypt.checkpw(in_passwd.encode('ascii'), user.password):
        # Authenticated, return a JWT
        ret = {
            'access_token': create_access_token(identity=user)
        }
        return jsonify(ret), 200
    else:
        # Authentication error
        return jsonify({'msg': 'bad user credentials'}), 401

@app.route('/me')
@jwt_required
def me():
    # Get user information from the id in the identity
    user_id = get_jwt_identity()
    user = db.session.query(User).filter_by(id=user_id).first()

    return jsonify({
        'id': user_id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'participates': [ {'id': org.id, 'name': org.name}
                          for org in user.participates ],
        'moderates': [ {'id': org.id, 'name': org.name}
                       for org in user.moderates ],
        'passes': pass_util.get_user_passes(user_id)

    }), 200

@app.route('/me/passes')
@jwt_required
def me_passes():
    return jsonify({
        'passes': pass_util.get_user_passes(get_jwt_identity())
    }), 200

@app.route('/org', methods=['POST'])
@jwt_required
def org_create():
    name = request.form.get('name')
    if name == None:
        return jsonify({
            'msg': 'missing org name'
        }), 422

    org = Org(name=name)
    db.session.add(org)

    # Make this user a moderator
    user = db.session.query(User).filter_by(id=get_jwt_identity()).first()
    org.mods.append(user)
    db.session.commit()

    return jsonify({
        'msg': 'success',
        'org_id': org.id
    }), 200

# Give the user a new pass (or at least request one).
@app.route('/org/<org_id>/pass', methods=['POST'])
@jwt_required
def me_request_pass(org_id):
    user_id = get_jwt_identity()

    state_id = request.form.get('state_id')
    spot_num = request.form.get('spot_num')

    err = None
    if state_id == None:
        err = {
            'msg': 'missing state_id'
        }
    elif spot_num == None:
        err = {
            'msg': 'missing spot_num'
        }

    if err != None:
        return jsonify(err), 422

    # Create a new request in the request log
    req = Pass(org_id = org_id,
               owner_id = user_id,
               requested_state_id = state_id,
               requested_spot_num = spot_num,
               request_time = datetime.now())

    db.session.add(req)
    db.session.commit()

    return jsonify({
        'pass_id': req.id
    }), 200

@app.route('/org/<org_id>')
@jwt_optional
def org_get(org_id):
    # Find the org by id
    org = db.session.query(Org).filter_by(id=org_id).first()

    if org is None:
        return jsonify({
            'msg': 'org not found'
        }), 404

    # Include basic information for all users
    ret = {
        'id': org.id,
        'name': org.name
    }

    # See if we are being accessed by a user who participates or moderates this
    # organization. We could technically store this information in the access
    # token, but its more straightforward if we just do it this way.
    user = db.session.query(User).filter_by(id=get_jwt_identity()).first()

    if user:
        if org in user.participates:
            # The user will need this.
            ret.update({
                'day_state_greeting_fmt': org.day_state_greeting_fmt or '',
                'parking_rules': json.loads(org.parking_rules or '{}'),
            })
        if org in user.moderates:
            ret.update({
                'unverified_passes': pass_util.get_org_unverified_passes(org.id)
            })

    return jsonify(ret), 200

# Add this so that we can do this live with AJAX or something
@app.route('/org/<org_id>/unverified_passes')
@jwt_required
def org_unverified_passes(org_id):
    user = db.session.query(User).filter_by(id=get_jwt_identity()).first()

    # Is there any way to avoid this query in order to check if a user is a mod?
    org = db.session.query(Org).filter_by(id=org_id).first()

    if org not in user.moderates:
        return jsonify({
            'msg': 'user {} must moderate org {}'.format(user.id, org_id)
        }), 403

    return jsonify({
        'unverified_passes': pass_util.get_org_unverified_passes(org_id)
    }), 200

@app.route('/org/<org_id>/assign_pass', methods=['POST'])
@jwt_required
def org_verify_pass(org_id):
    pass_id = request.form.get('pass_id')
    if pass_id == None:
        return jsonify({
            'msg': 'missing pass_id'
        }), 422

    state_id = request.form.get('state_id')
    spot_num = request.form.get('spot_num')

    p = db.session.query(Pass).filter_by(id=pass_id).first()
    if p == None:
        return jsonify({
            'msg': 'nonexistent pass {}'.format(pass_id)
        }), 422

    p.assigned_time = datetime.now()
    p.assigned_state_id = state_id or p.requested_state_id
    p.assigned_spot_num = spot_num or p.requested_spot_num
    db.session.commit()

    return jsonify({
        'msg': 'success'
    }), 200

@app.route('/org/search')
def org_search():
    query = request.args.get('q')
    if query == None:
        return jsonify({
            'msg': 'no query string'
        }), 422

    orgs = db.session.query(Org).filter(Org.name.like('%' + query + '%')).all()
    return jsonify([{'id': org.id, 'name': org.name } for org in orgs]), 200

class MissingDateError(Exception):
    def __str__(self):
        return 'must provide date *or* start_date and end_date'

class EndDateTooEarlyError(Exception):
    def __str__(self):
        return 'start_date must come before end_date'

def get_date_pair(date_in, start_date_in, end_date_in):
    start_date = None
    end_date = None

    if date_in != None:
        date = datetime.strptime(date_in, DATE_FMT)
        start_date = date
        end_date = date
    else:
        if start_date_in == None or end_date_in == None:
            raise MissingDateError
        else:
            start_date = datetime.strptime(start_date_in, DATE_FMT)
            end_date = datetime.strptime(end_date_in, DATE_FMT)

    if end_date < start_date:
        raise EndDateTooEarlyError

    return start_date, end_date

def get_live_org(org_id):
    if org_id not in live_orgs:
        live_orgs[org_id] = LiveOrg(redis, org_id)

    return live_orgs[org_id]

@app.route('/pass/borrow', methods=['POST'])
@jwt_required
def borrow_pass():
    user_obj = db.session.query(User).filter_by(id=get_jwt_identity()).first()
    if user_obj == None:
        return jsonify({
            'msg': "user {} doesn't exist, this is really bad".format(pass_id)
        }), 404

    # Make sure we were also given an org id.
    org_id = request.form.get('org_id')
    if org_id == None:
        return jsonify({
            'msg': 'missing org'
        }), 422

    try:
        start_date, end_date = get_date_pair(request.form.get('date'),
                                             request.form.get('start_date'),
                                             request.form.get('end_date'))
    except (MissingDateError, EndDateTooEarlyError) as e:
        return jsonify({
            'msg': str(e)
        }), 422

    live_org = get_live_org(org_id)

    ret_obj = {}
    for date in range_inclusive_dates(start_date, end_date):
        enqueued = live_org.enqueue_user_borrow(date, user_obj.id)
        ret_obj[date.strftime(DATE_FMT)] = {
            'enqueued': enqueued
        }

    return jsonify(ret_obj), 200

@app.route('/pass/<pass_id>/lend', methods=['POST'])
@jwt_required
def lend_pass(pass_id):
    # Make sure we were given a valid pass

    pass_obj = db.session.query(Pass).filter_by(id=pass_id).first()
    if pass_obj == None:
        return jsonify({
            'msg': "pass {} doesn't exist".format(pass_id)
        }), 404

    try:
        start_date, end_date = get_date_pair(request.form.get('date'),
                                             request.form.get('start_date'),
                                             request.form.get('end_date'))
    except (MissingDateError, EndDateTooEarlyError) as e:
        return jsonify({
            'msg': str(e)
        }), 422

    live_org = get_live_org(pass_obj.org_id)

    ret_obj = {}
    for date in range_inclusive_dates(start_date, end_date):
        enqueued = live_org.enqueue_pass_lend(date, pass_obj.id)
        ret_obj[date.strftime(DATE_FMT)] = {
            'enqueued': enqueued
        }

    # Should we have a way to mark a queue as retired? Or should that be
    # inferred based on whether the queue is in the org's active-queue list.
    return jsonify(ret_obj), 200
