# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

from flask import Blueprint, jsonify, request, current_app, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required

from pytz import all_timezones

from .. import util, exceptions as ex
from ..models import db, Org, User, Daystate
from ..util import jwt_optional, get_redis
from ..view_util import user_is_mod, user_is_participant, get_field, \
    get_org_by_id, get_user_by_id, daystate_exists
from ..worker import LiveOrg

org_api = Blueprint('org', __name__)


@org_api.route('/', methods=['POST'])
@jwt_required
def create_org():
    name = get_field(request, 'name')
    timezone = get_field(request, 'timezone')

    if timezone not in all_timezones:
        raise ex.InvalidTimezoneError(timezone)

    org = Org(name=name, timezone=timezone)
    db.session.add(org)

    # Make this user a moderator
    user = db.session.query(User).filter_by(id=get_jwt_identity()).first()
    org.mods.append(user)
    db.session.commit()

    return current_app.make_response(('', 201, {
        'Location': url_for('.orgs_query', org_id=org.id)
    }))


@org_api.route('/<org_id>')
@jwt_optional
def orgs_query(org_id):
    org = get_org_by_id(org_id)

    # Include basic information for all users
    ret = {
        'id': org.id,
        'name': org.name
    }

    user_id = get_jwt_identity()
    if user_is_participant(user_id, org_id) or user_is_mod(user_id, org_id):
        # Provide the timezone in the object
        ret.update({'timezone': org.timezone})

    return jsonify(ret), 200


@org_api.route('/search')
def orgs_search():
    query = request.args.get('q') or ''
    orgs = db.session.query(Org).filter(Org.name.like('%' + query + '%')).all()
    return jsonify([{'id': org.id, 'name': org.name} for org in orgs]), 200


# Org participants
@org_api.route('/<org_id>/participants', methods=['GET', 'POST'])
def org_participants(org_id):
    org = get_org_by_id(org_id)

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
        raise ex.Forbidden(
            'user {} must moderate or participate in org {}'
            .format(client_user_id, org_id)
        )

    if request.method == 'POST':
        # Make sure we were given a valid id
        participant_id = get_field(request, 'user_id')

        # And that the ID represents a valid user
        participant = get_user_by_id(participant_id)

        # Only allow regular participants to add themselves.
        if not mod_request and participant_id != client_user_id:
            raise ex.Forbidden(
                'participant {} should only be adding itself'
                .format(participant_id)
            )

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
            return jsonify(
                [util.user_dict(user) for user in org.participants]
            ), 200
        else:
            # They know what they did wrong.
            raise ex.Forbidden('Regular users cannot make this request')


@org_api.route('/<org_id>/participants/<user_id>')
@jwt_required
def org_participants_query(org_id, user_id):
    org = get_org_by_id(org_id)

    # Is the user a participant?
    user = get_user_by_id(user_id)

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
        raise ex.Forbidden(
            'user {} must moderate or participate in org {}'.format(
                client_user_id, org_id
            )
        )


# Org moderators
@org_api.route('/<org_id>/moderators', methods=['GET', 'POST'])
@jwt_required
def org_moderators(org_id):
    org = get_org_by_id(org_id)

    client_user_id = get_jwt_identity()
    if request.method == 'POST':
        # The client must be a mod
        if not user_is_mod(client_user_id, org_id):
            raise ex.Forbidden(
                'user {} must moderate org {}'.format(
                    client_user_id, org_id
                )
            )

        js = request.get_json()

        # Make sure we were given a valid id
        mod_id = js.get('user_id')
        if mod_id is None:
            return jsonify({
                'msg': 'missing user_id'
            }), 422

        # And that the ID represents a valid user
        mod = get_user_by_id(mod_id)

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
        return jsonify(
            [util.user_dict(user) for user in org.moderators]
        ), 200


@org_api.route('/<org_id>/moderators/<user_id>')
@jwt_required
def org_moderators_query(org_id, user_id):
    org = get_org_by_id(org_id)

    # Does our client moderate the org?
    client_user_id = get_jwt_identity()
    if not user_is_mod(client_user_id, org_id):
        # Get outta here
        raise ex.Forbidden(
            'user {} must moderate org {}'.format(client_user_id, org_id)
        )

    # Does the given user moderate?
    user = User.query.filter_by(id=user_id).first()

    if user in org.mods:
        return jsonify(util.user_dict(user)), 200
    else:
        return jsonify({
            'msg': 'user {} does not moderate org {}'.format(user_id, org_id)
        }), 404


# Day states

@org_api.route('/<org_id>/daystates', methods=['GET', 'POST'])
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
            raise ex.Forbidden(
                'user {} must mod org {}'.format(user_id, org_id)
            )

        # Post a new day state
        daystate = Daystate(org_id=org_id,
                            identifier=get_field(request, 'identifier'),
                            greeting=get_field(request, 'greeting'))
        db.session.add(daystate)
        db.session.commit()

        # Return the state location
        return current_app.make_response(('', 201, {
            'Location': url_for('org_daystates_query', org_id=org_id,
                                daystate_id=daystate.id)
        }))
    else:
        # The user must be a participant or mod.
        if not (user_is_mod(user_id, org_id) or
                    user_is_participant(user_id, org_id)):
            raise ex.Forbidden(
                'user {} not allowed to query daystates for org {}'
                .format(user_id, org_id)
            )

        # Query org day states by org id
        daystates = Daystate.query.filter_by(org_id=org_id).all()

        return jsonify(
            [{
                 'id': state.id,
                 'org_id': state.org_id,
                 'identifier': state.identifier,
                 'greeting': state.greeting
             } for state in daystates]
        ), 200

@org_api.route('/<org_id>/daystate_sequence', methods=['GET', 'POST'])
def org_daystate_sequence(org_id):
    # Construct a live org
    live_org = LiveOrg(get_redis(), get_org_by_id(org_id))
    if request.method == 'POST':
        # This should be an array of ints / ids
        daystate_seq = get_field(request, 'daystate_sequence')

        for daystate_id in daystate_seq:
            if not daystate_exists(daystate_id, org_id):
                raise ex.InvalidDaystate(daystate_id, org_id)

        live_org.set_state_sequence(daystate_seq)
    else:
        return jsonify({
            'org': org_id,
            'daystate_sequence': live_org.get_state_sequence()
        }), 200

# Technically, daystates are separate from orgs, but we want the client to know
# what org a given day state ID applies for. That is to say that all daystates
# will have unique IDs.
@org_api.route('/<org_id>/daystates/<daystate_id>', methods=['GET', 'PUT'])
@jwt_required
def org_daystates_query(org_id, daystate_id):
    # Find the day state in question
    daystate = Daystate.query.filter_by(id=daystate_id, org_id=org_id).first()

    # Is it valid?
    if daystate is None:
        return jsonify({
            'msg': 'daystate not found'
        }), 404

    user_id = get_jwt_identity()
    if request.method == 'PUT':

        # Make sure the user is mod
        if not user_is_mod(user_id, org_id):
            raise ex.Forbidden(
                'user {} must moderate org {}'.format(user_id, org_id)
            )

        js = request.get_json()
        new_identifier = js.get('identifier')
        new_greeting = js.get('greeting')

        if new_identifier:
            daystate.identifier = new_identifier
        if new_greeting:
            daystate.greeting = new_greeting

        db.session.commit()

    else:
        # If the user is trying to get info about this day state they must be a
        # participant.

        if not (user_is_participant(user_id, org_id) or
                    user_is_mod(user_id, org_id)):
            raise ex.Forbidden(
                'user {} must mod or participate in org {}'.format(
                    user_id, org_id
                )
            )

    # If they made it this far they are allowed to see the day state.
    return jsonify(util.daystate_dict(daystate)), 200


@org_api.route('/<org_id>/daystates/current')
@jwt_required
def org_daystates_current(org_id):
    user_id = get_jwt_identity()
    if not (user_is_participant(user_id, org_id) or
                user_is_mod(user_id, org_id)):
        raise ex.Forbidden(
            'user {} must mod or participate in org {}'.format(
                user_id, org_id
            )
        )

    live_org = LiveOrg(get_redis(), get_org_by_id(org_id))

    # Get the datetime of the start of today ie 00:00:00.
    today = live_org.date_util.today()

    # Use the aware datetime to find the daystate today.
    daystate = Daystate.query.filter_by(
        org_id=org_id,
        id=live_org.get_daystate_id(today)
    ).first()
    return jsonify(util.daystate_dict(daystate)), 200

@org_api.route('/<org_id>/rules', methods=['GET', 'PUT', 'POST'])
def org_rules(org_id):
    # When the client uses GET we want to query rules only, when they use
    # POST we only want to add rules, throwing an error if a rule already
    # exists in its place. If the client uses PUT we will allow them to
    # modify an existing rule.
    live_org = LiveOrg(get_redis(), get_org_by_id(org_id))
    if request.method == 'GET':
        pass
    elif request.method == 'PUT':
        pass
    else:
        pass
