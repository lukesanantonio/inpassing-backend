# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, \
    create_access_token

from .. import util, pass_util
from ..models import db, User

user_api = Blueprint('auth', __name__)


# Idea: Add anonymous auth @ GET /auth/anon.jwt or something
@user_api.route('/auth', methods=['POST'])
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


@user_api.route('/', methods=['POST'])
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

    if err is not None:
        return jsonify(err), 422

    # Hash password, add user, return response.
    hashpass = bcrypt.hashpw(password.encode('ascii'), bcrypt.gensalt(12))
    user_obj = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=hashpass
    )
    db.session.add(user_obj)
    db.session.commit()

    return jsonify({
        'user_id': user_obj.id,
        'msg': 'successfully created new user'
    }), 200


@user_api.route('/me')
@jwt_required
def me():
    # Get user information from the id in the identity
    user_id = get_jwt_identity()
    user_obj = db.session.query(User).filter_by(id=user_id).first()

    user_dict = util.user_dict(user_obj)
    user_dict['passes'] = [
        util.pass_dict(pas)
        for pas in pass_util.query_user_passes(db.session, user_id)
        ]
    return jsonify(user_dict), 200
