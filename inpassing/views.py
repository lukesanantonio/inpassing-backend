# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import request, jsonify, url_for

from . import pass_util
from .app import app

from . import models
from .models import Org, User, Pass, Daystate, db

from . import util
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

def user_is_participant(user_id, org_id):
    q = db.session.query(models.org_participants).filter_by(
        participant=user_id, org=org_id
    )
    (ret,) = db.session.query(q.exists()).first()
    return ret

def user_is_mod(user_id, org_id):
    q = db.session.query(models.org_mods).filter_by(mod=user_id, org=org_id)
    (ret,) = db.session.query(q.exists()).first()
    return ret

# Orgs

@app.route('/orgs', methods=['POST'])
@jwt_required
def create_org():
    name = request.get_json().get('name', None)
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

    return app.make_response(('', 201, {
        'Location': url_for('orgs_query', org_id=org.id)
    }))

@app.route('/orgs/<org_id>')
@jwt_optional
def orgs_query(org_id):
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

    return jsonify(ret), 200

@app.route('/orgs/search')
def orgs_search():
    query = request.args.get('q') or ''
    orgs = db.session.query(Org).filter(Org.name.like('%' + query + '%')).all()
    return jsonify([{'id': org.id, 'name': org.name } for org in orgs]), 200

# Org participants
@app.route('/orgs/<org_id>/participants', methods=['GET', 'POST'])
def org_participants(org_id):

    org = Org.query.filter_by(id=org_id).first()
    if org == None:
        return jsonify({
            'msg': 'org not found'
        }), 404

    client_user_id = get_jwt_identity()

    if user_is_mod(client_user_id, org_id):
        # If the user is a mod we are going to make whoever they want
        # participate, guaranteed.
        mod_request = True
    elif user_is_participant(client_user_id, org_id):
        # If the user is a participant we take their user as a suggestion
        mod_request = False
    else:
        # Otherwise fuck'em
        return jsonify({
            'msg': 'user {} must moderate or participate in org {}'.format(
                client_user_id, org_id
            )
        }), 403

    if request.method == 'POST':
        js = request.get_json()

        # Make sure we were given a valid id
        participant_id = js.get('user_id')
        if participant_id == None:
            return jsonify({
                'msg': 'missing user_id'
            }), 422

        # And that the ID represents a valid user
        participant = User.query.filter_by(id=participant_id).first()
        if participant == None:
            return jsonify({
                'msg': 'unknown user {}'.format(participant_id)
            }), 422

        # Only allow regular participants to add themselves.
        if not mod_request and participant_id != client_user_id:
            return jsonify({
                'msg': 'participant {} should only be adding itself'
            }), 422

        # Make sure that the participant to be is not already a participant
        if participant in org.participants:
            return jsonify({
                'msg': 'user {} already participates in org {}'.format(
                    participant_id, org_id
                )
            }), 204

        # Do it now!
        org.participants.append(participant)
        db.session.commit()

        return '', 204

    else:
        # The method is GET
        if mod_request:
            # Return all participants
            return jsonify([
                util.user_dict(user) for user in org.participants
            ]), 200
        else:
            # They know what they did wrong.
            return '', 403

@app.route('/orgs/<org_id>/participants/<user_id>')
@jwt_required
def org_participants_query(org_id, user_id):
    # Find the org in question
    org = Org.query.filter_by(id=org_id).first()
    if org == None:
        return jsonify({
            'msg': 'org not found'
        }), 404

    # Is the user a participant?
    user = User.query.filter_by(user_id).first()

    if user in org.participants:
        participating = True
    else:
        participating = False

    user_ret = jsonify(util.user_dict(user)), 200
    no_part_ret = jsonify({
        'msg': 'user {} does not participate in org {}'.format(user_id, org_id)
    }), 404

    # If the client is a mod, let them see this unrestricted.
    client_user_id = get_jwt_identity()

    # This logic could be less redundant but I think its clear what is going on
    # its current form. Basically, if the user is a participant they can only
    # really query their own object as an easy check to see if a user
    # participates in a given org. For mods though they can query any user
    # object, or the entire list with the endpoint above.
    if user_is_participant(client_user_id, org_id):
        if client_user_id == user_id and participating:
            # The user is asking if they are participating in this org, and they
            # are.
            return user_ret
        else:
            # No matter who it is and if they're participating, we won't tell
            # this random client.
            return no_part_ret
    elif user_is_mod(client_user_id, org_id):
        # The user is a mod, they can query whatever they want.
        if participating:
            return user_ret
        else:
            return no_part_ret
    else:
        return jsonify({
            'msg': 'user {} must moderate or participate in org {}'.format(
                client_user_id, org_id
            )
        }), 403

# Org moderators
@app.route('/orgs/<org_id>/moderators', methods=['GET', 'POST'])
@jwt_required
def org_moderators(org_id):

    org = Org.query.filter_by(id=org_id).first()
    if org == None:
        return jsonify({
            'msg': 'org not found'
        }), 404

    client_user_id = get_jwt_identity()
    if request.method == 'POST':
        # The client must be a mod
        if not user_is_mod(client_user_id, org_id):
            return jsonify({
                'msg': 'user {} must moderate org {}'.format(
                    client_user_id, org_id
                )
            }), 403

        js = request.get_json()

        # Make sure we were given a valid id
        mod_id = js.get('user_id')
        if mod_id == None:
            return jsonify({
                'msg': 'missing user_id'
            }), 422

        # And that the ID represents a valid user
        mod = User.query.filter_by(id=mod_id).first()
        if mod == None:
            return jsonify({
                'msg': 'unknown user {}'.format(mod_id)
            }), 422

        # Make sure that the participant to be is not already a participant
        if mod in org.mods:
            return jsonify({
                'msg': 'user {} already moderates org {}'.format(
                    mod_id, org_id
                )
            }), 204

        # Do it now!
        org.mods.append(mod)
        db.session.commit()

        return '', 204

    else:
        # The method is GET so return all moderators
        return jsonify([
            util.user_dict(user) for user in org.moderators
        ]), 200

@app.route('/orgs/<org_id>/moderators/<user_id>')
@jwt_required
def org_moderators_query(org_id, user_id):
    # Find the org in question
    org = Org.query.filter_by(id=org_id).first()
    if org == None:
        return jsonify({
            'msg': 'org not found'
        }), 404

    # Does our client moderate the org?
    client_user_id = get_jwt_identity()
    if not user_is_mod(client_user_id, org_id):
        # Get outta here
        return jsonify({
            'msg': 'user {} must moderate org {}'.format(client_user_id, org_id)
        }), 403

    # Does the given user moderate?
    user = User.query.filter_by(id=user_id).first()

    if user in org.mods:
        return jsonify(util.user_dict(user)), 200
    else:
        return jsonify({
            'msg': 'user {} does not moderate org {}'.format(user_id, org_id)
        }), 404

# Day states

@app.route('/orgs/<org_id>/daystates', methods=['GET', 'POST'])
@jwt_required
def org_daystates(org_id):

    # Check to see if the org exists
    org_q = db.session.query(Org).filter_by(id=org_id)
    (org_exists,) = db.session.query(org_q.exists()).first()

    if not org_exists:
        return jsonify({
            'msg': 'org not found'
        }), 404

    user_id = get_jwt_identity()
    if request.method == 'POST':
        # The user must be a mod
        if not user_is_mod(user_id, org_id):
            return jsonify({
                'msg': 'user {} must mod org {}'.format(user_id, org_id)
            }), 403

        # Post a new day state
        data = request.get_json()

        if 'identifier' not in data:
            return jsonify({
                'msg': 'missing daystate identifier'
            }), 422

        if 'greeting' not in data:
            return jsonify({
                'msg': 'missing daystate greeting'
            }), 422

        daystate = Daystate(org_id = org_id,
                            identifier = data['identifier'],
                            greeting = data['greeting'])
        db.session.add(daystate)
        db.session.commit()

        # Return the state location
        return app.make_response(('', 201, {
            'Location': url_for('org_daystates_query', org_id=org_id,
                                daystate_id=daystate.id)
        }))
    else:
        # The user must be a participant or mod.
        if not (user_is_mod(user_id, org_id) or
                user_is_participant(user_id, org_id)):
            return jsonify({
                'msg': ('user {} not allowed to query daystates for org {}'
                        .format(user_id, org_id))
            }), 403

        # Query org day states by org id
        daystates = Daystate.query.filter_by(org_id=org_id).all()

        return jsonify([{
            'id': state.id,
            'org_id': state.org_id,
            'identifier': state.identifier,
            'greeting': state.greeting
        } for state in daystates]), 200

# Technically, daystates are separate from orgs, but we want the client to know
# what org a given day state ID applies for. That is to say that all daystates
# will have unique IDs.
@app.route('/orgs/<org_id>/daystates/<daystate_id>', methods=['GET', 'PUT'])
@jwt_required
def org_daystates_query(org_id, daystate_id):

    # Find the day state in question
    daystate = Daystate.query.filter_by(id=daystate_id, org_id=org_id).first()

    # Is it valid?
    if daystate == None:
        return jsonify({
            'msg': 'daystate not found'
        }), 404

    user_id = get_jwt_identity()
    if request.method == 'PUT':

        # Make sure the user is mod
        if not user_is_mod(user_id, org_id):
            return jsonify({
                'msg': 'user {} must moderate org {}'.format(user_id, org_id)
            }), 403

        js = request.get_json()
        new_identifier = js.get('identifier')
        new_greeting = js.get('greeting')

        if new_identifier:
            daystate.identifier = new_identifier
        if new_greeting:
            daystate.greeting = new_greeting

        db.session.commit()

    else:
        # If the user is trying to get info about this game state they must be a
        # participant.

        if not (user_is_participant(user_id, org_id) or
                user_is_mod(user_id, org_id)):
            return jsonify({
                'msg': 'user {} must mod or participate in org {}'.format(
                    user_id, org_id
                )
            }), 403

    # If they made it this far they are allowed to see the day state.
    return jsonify(util.daystate_dict(daystate)), 200

@app.route('/orgs/<org_id>/daystates/current')
@jwt_required
def org_daystates_current(org_id):

    user_id = get_jwt_identity()
    if not (user_is_participant(user_id, org_id) or
            user_is_mod(user_id, org_id)):
        return jsonify({
            'msg': 'user {} must mod or participate in org {}'.format(
                user_id, org_id
            )
        }), 403

    # TODO: Tie this into the live org / worker implementation somehow!
    daystate = Daystate.query.filter_by(org_id=org_id).first()
    return jsonify(util.daystate_dict(daystate)), 200
@app.route('/user/signup', methods=['POST'])
def user_signup():
    first_name = request.get_json().get('first_name')
    last_name = request.get_json().get('last_name')
    email = request.get_json().get('email')
    password = request.get_json().get('password')

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
    in_email = request.get_json().get('email', '')
    in_passwd = request.get_json().get('password', '')

    user = db.session.query(User).filter_by(email=in_email).first()

    if user and bcrypt.checkpw(in_passwd.encode('ascii'), user.password):
        # Authenticated, return a JWT
        ret = {
            'access_token': create_access_token(identity=user)
        }
        return jsonify(ret), 200
    else:
        # Authentication error
        return jsonify({'msg': 'invalid username or password'}), 401

@app.route('/me')
@jwt_required
def me():
    # Get user information from the id in the identity
    user_id = get_jwt_identity()
    user = db.session.query(User).filter_by(id=user_id).first()

    user_obj = util.user_dict(user)
    user_obj['passes'] = [
        util.pass_dict(pas)
        for pas in pass_util.query_user_passes(db.session, user_id)
    ]
    return jsonify(user_obj), 200


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

@app.route('/me/borrow', methods=['POST'])
@jwt_required
def me_borrow():
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


@app.route('/me/unborrow')
@jwt_required
def me_unborrow():
    pass

# Give the user a new pass (or at least request one).
@app.route('/org/<org_id>/pass', methods=['POST'])
@jwt_required
def me_request_pass(org_id):
    user_id = get_jwt_identity()

    # Make sure the user is allowed to participate
    if not user_is_participant(user_id, org_id):
        return jsonify({
            'msg': 'user {} must participate in org {}'.format(user_id, org_id)
        }), 403

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

# Add this so that we can do this live with AJAX or something
@app.route('/org/<org_id>/passes')
@jwt_required
def org_passes(org_id):
    user = db.session.query(User).filter_by(id=get_jwt_identity()).first()

    # Is there any way to avoid this query in order to check if a user is a mod?
    org = db.session.query(Org).filter_by(id=org_id).first()

    if org not in user.moderates:
        return jsonify({
            'msg': 'user {} must moderate org {}'.format(user.id, org_id)
        }), 403

    return jsonify({
        'passes': [util.pass_dict(p) for p in passes]
    }), 200

@app.route('/org/<org_id>/pass/<pass_id>')
@jwt_required
def org_pass_get(org_id, pass_id):
    # TODO: Some way to make sure the user is a mod.
    p = db.session.query(Pass).filter(
        and_(Pass.id == pass_id, Pass.org_id == org_id)
    ).first()

    if p == None:
        return jsonify('nonexistent pass {}'.format(pass_id)), 404

    return jsonify({
        'pass': util.pass_dict(p)
    }), 200


@app.route('/org/<org_id>/pass/<pass_id>/assign', methods=['PUT'])
@jwt_required
def org_pass_assign(org_id, pass_id):
    # Find the pass
    p = db.session.query(Pass).filter(
        and_(Pass.id == pass_id, Pass.org_id == org_id)
    ).first()

    if p == None:
        return jsonify({
            'msg': 'nonexistent pass {}'.format(pass_id)
        }), 422

    user_id = get_jwt_identity()
    if p.owner_id != user_id:
        return jsonify({
            'msg': 'pass {} not owned by user {}'.format(pass_id, user_id)
        }), 403

    p.assigned_time = datetime.now()
    p.assigned_state_id = request.form.get('state_id', p.requested_state_id)
    p.assigned_spot_num = request.form.get('spot_nyum', p.requested_spot_num)
    db.session.commit()

    return jsonify({
        'msg': 'success',
        'pass': util.pass_dict(p),
    }), 200

@app.route('/pass/<pass_id>/lend', methods=['POST'])
@jwt_required
def lend_pass(pass_id):
    pass_obj = db.session.query(Pass).filter_by(id=pass_id).first()
    if pass_obj == None:
        return jsonify({
            'msg': "pass {} doesn't exist".format(pass_id)
        }), 404

    user_id = get_jwt_identity()
    if pass_obj.owner_id != user_id:
        # The user doesn't own this pass!
        return jsonify({
            'msg': 'pass {} not owned by user {}'.format(pass_id, user_id)
        }), 403

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
