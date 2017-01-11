# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager

from . import default_config, models, views, exceptions as ex


def create_app(config_obj=None, suppress_env_config=False, **kwargs):
    app = Flask(__name__, **kwargs)

    app.register_blueprint(views.user_api, url_prefix='/users')
    app.register_blueprint(views.pass_api, url_prefix='/passes')
    app.register_blueprint(views.org_api, url_prefix='/orgs')

    app.config.from_object(default_config)

    if not suppress_env_config:
        # Look for config.py in a given instance folder
        app.config.from_pyfile('config.py', silent=True)

        # As a last ditch effort, check the file given by the environment
        # variable. It could be used in place of config.py to point to
        # alternative configuration files (production and debug, for example).
        app.config.from_envvar('INPASSING_CONFIG', silent=True)

    if config_obj:
        app.config.from_object(config_obj)

    # Handle InPassing Exception types
    @app.errorhandler(ex.InPassingException)
    def generic_exception_handler(e):
        return jsonify({
            'err': e.get_err(),
            'msg': e.get_msg()
        }), e.get_code()

    # Init SQLAlchemy
    models.db.init_app(app)

    # Init Redis
    views.redis_store.init_app(app)

    # Init JWT Helper
    jwt = JWTManager(app)

    # Users are verified by ID
    @jwt.user_identity_loader
    def user_identity(user):
        return user.id

    return app
