# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import request, jsonify

from . import pass_util
from .app import app
from .models import Org, User, db

from .utils import jwt_optional

import json
import bcrypt

from flask_jwt_extended import JWTManager, jwt_required, create_access_token,\
    create_refresh_token, jwt_refresh_token_required, get_jwt_identity

jwt = JWTManager(app)

@jwt.user_identity_loader
def user_identity(ident):
    # The user is identified with their ID.
    return ident.id

@app.route('/auth/user.jwt', methods=['POST'])
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

@app.route('/me/pass_request', methods=['POST'])
@jwt_required
def me_request_pass():
    user_id = get_jwt_identity()

    org_id = request.form.get('org_id')
    state_id = request.form.get('state_id')
    spot_num = request.form.get('spot_num')

    err = None
    if org_id == None:
        err = {
            'msg': 'missing org_id'
        }
    elif state_id == None:
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
    req = PassRequest(org_id = org_id,
                      requestor_id = user_id,
                      state_id = state_id,
                      spot_num = spot_num)

    db.session.add(req)
    db.session.commit()

    return jsonify({
        'request_id': req.id
    }), 200

# Idea?
# @app.route('/me/pending_passes') *or*
# @app.route('/me/pending_requests') *and*
# @app.route('/me/owned_passes') *and*
# @app.route('/me/using_passes')

@app.route('/orgs/<org_id>')
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
            if org in user.moderates:
                # We don't have any more information to give out to moderators.
                pass

            # The user will need this.
            ret.update({
                'day_state_greeting_fmt': org.day_state_greeting_fmt or '',
                'parking_rules': json.loads(org.parking_rules or '{}'),
            })

    return jsonify(ret), 200
