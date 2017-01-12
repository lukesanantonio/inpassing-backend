# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import datetime

from flask import Blueprint, jsonify, request, current_app, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_redis import FlaskRedis

from .. import util
from ..models import db, User, Daystate, Pass
from ..util import range_inclusive_dates
from ..view_util import user_is_mod, user_is_participant, get_user_by_id, \
    get_field
from ..worker import LiveOrg, DATE_FMT

pass_api = Blueprint('pass', __name__)

redis_store = FlaskRedis()
live_orgs = {}


@pass_api.route('/', methods=['GET', 'POST'])
@jwt_required
def passes():
    user = get_user_by_id(get_jwt_identity())

    if request.method == 'GET':
        # Filter by org
        filter_org_id = request.args.get('org_id')

        # Filter by user
        filter_user_id = request.args.get('user_id')

        # Filter by verified or not
        filter_verified = request.args.get('verified')

        def allow_pass(p):
            allow = True
            if filter_org_id is not None:
                allow = (allow and p.org_id == filter_org_id)
            if filter_user_id is not None:
                allow = (allow and p.owner_id == filter_user_id)
            if filter_verified is not None:
                if filter_verified:
                    # We're looking for verified passes
                    allow = (allow and p.assigned_time is not None)
                else:
                    # We're looking for unverified passes
                    allow = (allow and p.assigned_time is None)

            return allow

        # Build a dict of all passes this user can access.

        # Passes owned by this user
        all_passes = user.passes[:]

        for org in user.moderates:
            # And all passes in all the orgs that this user moderates.
            all_passes.extend(org.passes[:])

        return jsonify({
            'passes': [util.pass_dict(p) for p in all_passes if allow_pass(p)]
        }), 200

    elif request.method == 'POST':
        # Request a new pass on behalf of the user
        # We verify that the org id is valid when we check the day state.
        org_id = get_field(request, 'org_id')
        state_id = get_field(request, 'state_id')

        # Make sure that state exists
        state_query = Daystate.query.filter_by(id=state_id, org_id=org_id)
        (exists,) = db.session.query(state_query.exists()).first()

        if not exists:
            return jsonify({
                'msg': 'bad state id'
            }), 422

        spot_num = get_field(request, 'spot_num')

        p = Pass()
        p.org_id = org_id
        p.requested_state_id = state_id
        p.requested_spot_num = spot_num
        p.request_time = datetime.datetime.now()

        owner_id = get_field(request, 'owner_id')

        # What is the authenticated user's relationship to the org?
        if user_is_mod(get_jwt_identity(), org_id):
            # Do whatever they say, now
            p.owner_id = owner_id or get_jwt_identity()
            p.assigned_state_id = state_id
            p.assigned_spot_num = spot_num
            p.assigner = get_jwt_identity()
            p.assigned_time = datetime.datetime.now()

        elif user_is_participant(get_jwt_identity(), org_id):
            # They can request a pass but only for themselves
            if owner_id is not None and owner_id != get_jwt_identity():
                return jsonify({
                    'msg': 'user cannot request a pass for something else'
                }), 403

            # A participant should only be requesting a pass for themselves.
            p.owner_id = get_jwt_identity()

        # Add the pass and return its uri.
        db.session.add(p)
        db.session.commit()
        return current_app.make_response(('', 201, {
            'Location': url_for('.passes_query', pass_id=p.id)
        }))


@pass_api.route('/<pass_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required
def passes_query(pass_id):
    # What pass?
    p = Pass.query.filter_by(id=pass_id).first()
    is_mod = user_is_mod(get_jwt_identity(), p.org_id)
    if request.method == 'GET':
        # Make sure the user is allowed to see this pass
        if is_mod or get_jwt_identity() == p.owner_id:
            # If the user moderates the org which the pass belongs to they are
            # allowed to see it. They can also just be the owner.
            return jsonify(util.pass_dict(p)), 200
        else:
            return jsonify({
                'msg': 'not authenticated to view this pass',
                'error_code': 'foreign_pass'
            }), 403
    elif request.method == 'PUT':
        # Only a mod is allowed to re-assign the pass
        if is_mod:
            # Wow, these align so well!
            new_state_id = get_field(request, 'state_id')
            new_spot_num = get_field(request, 'spot_num')
            new_owner_id = get_field(request, 'owner_id')

            modified = False

            if new_state_id is not None:
                # Make sure this is a valid state id
                state_q = Daystate.query.filter_by(
                    id=new_state_id, org_id=p.org_id
                )
                (exists,) = db.session.query(state_q.exists()).first()
                if not exists:
                    return jsonify({
                        'msg': 'state {} cannot be assigned to pass {}'.format(
                            new_state_id, p.id
                        )
                    }), 422
                # Assign the state ID
                p.assigned_state_id = new_state_id
                modified = True

            if new_spot_num is not None:
                p.assigned_spot_num = new_spot_num
                modified = True
            if new_owner_id is not None:
                p.owner_id = new_owner_id
                modified = True

            if modified:
                # Update time and commit!
                p.assigned_time = datetime.datetime.now()
                db.session.commit()

                return jsonify(util.pass_dict(p)), 200
            else:
                return jsonify({
                    'msg': 'nothing changed'
                }), 204
        else:
            return jsonify({
                'msg': 'not authenticated to modify this pass',
            }), 403
    elif request.method == 'DELETE':
        # If we are a mod, remove the pass immediately.
        if is_mod:
            db.session.remove(p)
            db.session.commit()

        ###
        # TODO: Make sure we update queues so that the pass isn't lent out.
        ###

        # If we are a participant we can only delete our own pass but this will
        # only remove the association of the user with the pass. This probably
        # won't break borrowing.
        if get_jwt_identity() == p.owner_id:
            # Remove our association
            p.owner_id = None
            db.session.commit()
            return '', 204
        else:
            return jsonify({
                'msg': 'not authorized to remove this pass'
            }), 403


class MissingDateError(Exception):
    def __str__(self):
        return 'must provide date *or* start_date and end_date'


class EndDateTooEarlyError(Exception):
    def __str__(self):
        return 'start_date must come before end_date'


def get_date_pair(date_in, start_date_in, end_date_in):
    if date_in is not None:
        date = datetime.datetime.strptime(date_in, DATE_FMT)
        start_date = date
        end_date = date
    else:
        if start_date_in is None or end_date_in is None:
            raise MissingDateError
        else:
            start_date = datetime.datetime.strptime(start_date_in, DATE_FMT)
            end_date = datetime.datetime.strptime(end_date_in, DATE_FMT)

    if end_date < start_date:
        raise EndDateTooEarlyError

    return start_date, end_date


def get_live_org(org_id):
    if org_id not in live_orgs:
        live_orgs[org_id] = LiveOrg(redis_store, org_id)

    return live_orgs[org_id]


def do_borrow(user_id, js, action):
    user_obj = User.query.filter_by(id=user_id).first()
    if user_obj is None:
        return jsonify({
            'msg': "user {} doesn't exist, this is really bad".format(user_id)
        }), 404

    # Make sure we were also given an org id.
    org_id = js.get('org_id')
    if org_id is None:
        return (jsonify({
            'msg': 'missing org'
        }), 422), True

    try:
        start_date, end_date = get_date_pair(
            js.get('date'), js.get('start_date'), js.get('end_date')
        )
    except (MissingDateError, EndDateTooEarlyError) as e:
        return (jsonify({
            'msg': str(e)
        }), 422), True

    live_org = get_live_org(org_id)
    return action(start_date, end_date, user_obj, live_org)


@pass_api.route('/borrow', methods=['POST'])
@jwt_required
def borrow_pass():
    def enqueue(start_date, end_date, user_obj, live_org):
        ret_obj = {}
        for date in range_inclusive_dates(start_date, end_date):
            enqueued = live_org.enqueue_user_borrow(date, user_obj.id)
            ret_obj[datetime.date.strftime(DATE_FMT)] = {
                'enqueued': enqueued
            }

        return jsonify(ret_obj), 200

    return do_borrow(get_jwt_identity, request.get_json(), enqueue)


@pass_api.route('/unborrow')
@jwt_required
def unborrow_pass():
    def dequeue(start_date, end_date, user_obj, live_org):
        ret_obj = {}
        for date in range_inclusive_dates(start_date, end_date):
            dequeued = live_org.dequeue_user_borrow(date, user_obj.id)
            ret_obj[datetime.date.strftime(DATE_FMT)] = {
                'dequeued': dequeued
            }

        return jsonify(ret_obj), 200

    return do_borrow(get_jwt_identity, request.get_json(), dequeue)


def do_lend(pass_id, user_id, js, action):
    pass_obj = Pass.query.filter_by(id=pass_id).first()
    if pass_obj is None:
        return jsonify({
            'msg': "pass {} doesn't exist".format(pass_id)
        }), 404

    if pass_obj.owner_id != user_id:
        # The user doesn't own this pass!
        return jsonify({
            'msg': 'pass {} not owned by user {}'.format(pass_id, user_id)
        }), 403

    try:
        start_date, end_date = get_date_pair(
            js.get('date'), js.get('start_date'), js.get('end_date')
        )
    except (MissingDateError, EndDateTooEarlyError) as e:
        return jsonify({
            'msg': str(e)
        }), 422

    live_org = get_live_org(pass_obj.org_id)

    return action(start_date, end_date, pass_obj, live_org)


@pass_api.route('/<pass_id>/lend', methods=['POST'])
@jwt_required
def lend_pass(pass_id):
    def enqueue(start_date, end_date, pass_obj, live_org):
        ret_obj = {}
        for date in range_inclusive_dates(start_date, end_date):
            enqueued = live_org.enqueue_pass_lend(date, pass_obj.id)
            ret_obj[datetime.date.strftime(DATE_FMT)] = {
                'enqueued': enqueued
            }

        # Should we have a way to mark a queue as retired? Or should that be
        # inferred based on whether the queue is in the org's active-queue list.
        return jsonify(ret_obj), 200

    return do_lend(pass_id, get_jwt_identity(), request.get_json(), enqueue)


@pass_api.route('/<pass_id>/unlend', methods=['POST'])
@jwt_required
def unlend_pass(pass_id):
    def dequeue(start_date, end_date, pass_obj, live_org):
        ret_obj = {}
        for date in range_inclusive_dates(start_date, end_date):
            dequeued = live_org.dequeue_pass_lend(date, pass_obj.id)
            ret_obj[datetime.date.strftime(DATE_FMT)] = {
                'dequeued': dequeued
            }
        return jsonify(ret_obj), 200

    return do_lend(pass_id, get_jwt_identity(), request.get_json(), dequeue)
