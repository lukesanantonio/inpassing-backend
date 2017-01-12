# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, \
    create_access_token

from .. import util, pass_util, exceptions as ex
from ..models import db, User
from ..view_util import get_field, get_user_by_id

user_api = Blueprint('auth', __name__)


# Idea: Add anonymous auth @ GET /auth/anon.jwt or something
@user_api.route('/auth', methods=['POST'])
def auth_user():
    in_email = get_field(request, 'email')
    in_passwd = get_field(request, 'password')

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
    # Does a user with this email already exist?
    email = get_field(request, 'email')
    user_email_q = User.query.filter_by(email=email)

    (user_exists,) = db.session.query(user_email_q.exists()).first()

    if user_exists:
        raise ex.UserExistsError()

    # Hash password, add user, return response.
    password = get_field(request, 'password')
    hashpass = bcrypt.hashpw(password.encode('ascii'), bcrypt.gensalt(12))
    user_obj = User(
        first_name=get_field(request, 'first_name'),
        last_name=get_field(request, 'last_name'),
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
    user_obj = get_user_by_id(user_id)

    user_dict = util.user_dict(user_obj)
    user_dict['passes'] = [
        util.pass_dict(pas)
        for pas in pass_util.query_user_passes(db.session, user_id)
        ]
    return jsonify(user_dict), 200
