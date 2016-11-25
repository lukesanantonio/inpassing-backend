# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import request, jsonify

from . import pass_util
from .app import app
from .models import Org, User, db

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

@app.route('/me/request_pass')
@jwt_required
def me_request_pass():
    user_id = get_jwt_identity()

    org_id = request.args.get('org_id')
    state_id = request.args.get('state_id')
    spot_num = request.args.get('spot_num')

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

@app.route('/orgs/<org_id>')
@jwt_required
def org_get(org_id):
    cur_user_id = get_jwt_identity()

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

    if cur_user_id in org.mods or cur_user_id in org.participants:
        ret.update({
            'day_state_greeting_fmt': org.day_state_greeting_fmt,
            'parking_rules': json.loads(org.parking_rules),
        })

    return jsonify(ret), 200
