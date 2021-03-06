# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import json
import re

from fixture import SQLAlchemyFixture
from flask_testing import TestCase

from . import data as test_data
from .. import models, exceptions as ex
from ..app import create_app


class testing_config:
    SECRET_KEY = 'this-key-is-only-for-testing'
    DEBUG = True
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


API_PREFIX = '/api/v1'

def auth_headers(token):
    return {'Authorization': 'Bearer ' + token}


class TestApp(TestCase):
    def create_app(self):
        return create_app(testing_config, suppress_env_config=True)

    def setUp(self):
        # Create tables
        models.db.create_all()

        # Load data
        fix = SQLAlchemyFixture(env=models, engine=models.db.engine)
        self.data = fix.data(*test_data.all_data)
        self.data.setup()

    def tearDown(self):
        self.data.teardown()

        models.db.session.remove()
        models.db.drop_all()

    def auth(self, user):
        res = self.client.post(
            API_PREFIX + '/users/auth', content_type='application/json',
            data='{"email": "' + user.email + '", "password": "password"}'
        )
        self.assert200(res)

        json_data = json.loads(res.get_data().decode())
        access_token = json_data.get('access_token')
        self.assertTrue(access_token)
        return access_token

    def test_bad_auth(self):
        res = self.client.post(
            API_PREFIX + '/users/auth', content_type='application/json',
            data='{"email": "madeupemail", "password": "password"}'
        )
        self.assert401(res)

    def _test_user(self, user, token=None):
        token = token or self.auth(user)

        res = self.client.get(API_PREFIX + '/users/me',
                              headers=auth_headers(token))
        self.assert200(res)
        self.assertEqual('application/json', res.content_type)

        me_obj = json.loads(res.get_data().decode())
        id = me_obj['id']

        # Assert some basic information
        self.assertEqual(user.first_name, me_obj.get('first_name'))
        self.assertEqual(user.last_name,  me_obj.get('last_name'))
        self.assertEqual(user.email,      me_obj.get('email'))

        return me_obj

    def test_regular_user(self):
        user_obj = self._test_user(test_data.User.user)

        self.assertEqual(1, len(user_obj.get('participates')))
        self.assertEqual(
            test_data.Org.locust_valley.name,
            user_obj['participates'][0]['name']
        )

        self.assertEqual([], user_obj.get('moderates'))

    def test_mod_user(self):
        user_obj = self._test_user(test_data.User.mod)

        self.assertEqual(1, len(user_obj.get('moderates')))
        self.assertEqual(
            test_data.Org.locust_valley.name, user_obj['moderates'][0]['name']
        )

        self.assertEqual([], user_obj.get('participates'))

    def test_user_create(self):
        user_init_data = {
            'first_name': 'Fake',
            'last_name': 'Name',
            'email': 'fakeemail@gmail.com',
            'password': 'password'
        }

        res = self.client.post(
            API_PREFIX + '/users/', content_type='application/json',
            data=json.dumps(user_init_data)
        )

        # Assert that the user was created properly, then try to create the same
        # user and verify that it fails

        self.assert200(res)

        user_init_data['first_name'] = 'New name'
        user_init_data['last_name'] = 'New last name'
        user_init_data['password'] = 'even a new password'

        res2 = self.client.post(
            API_PREFIX + '/users/', content_type='application/json',
            data=json.dumps(user_init_data)
        )

        # The request should have failed because of the user email already being
        # in use
        self.assertStatus(res2, 422)
        self.assertEqual(res2.json['err'], ex.UserExistsError.err)

    def test_org_public_interface(self):
        # TODO: Test access to orgs without authentication tokens
        pass

    def test_org_create(self):
        # A regular user should not be able to get this
        self.assert401(self.client.post(API_PREFIX + '/orgs/'))

        # Authenticate as a regular user, then try it again.
        token = self.auth(test_data.User.user)

        # This token is good as a regular user, create an org and see what
        # happens.
        ORG_NAME = 'My First Org'
        res = self.client.post(API_PREFIX + '/orgs/',
                               content_type='application/json',
                               data='{"name": "' + ORG_NAME + '"}',
                               headers=auth_headers(token))

        location = res.headers['Location']

        match = re.match('.*/orgs/(\d)', location)
        self.assertTrue(match)
        org_id = int(match.group(1))

        res = self.client.get(location)
        org_obj = json.loads(res.get_data().decode())

        self.assertEqual(org_obj['name'], ORG_NAME)
        self.assertEqual(org_obj['id'], org_id)

        me_obj = self._test_user(test_data.User.user, token)

        # Make sure the user is a mod of the org
        self.assertEqual(1, len(me_obj['moderates']))
        self.assertEqual(org_id, int(me_obj['moderates'][0]['id']))
        self.assertEqual(ORG_NAME, me_obj['moderates'][0]['name'])

        # Get the moderator object through this interface, which should only
        # work if we are a moderator of that org.
        res = self.client.get(
            API_PREFIX + '/orgs/{}/moderators/{}'.format(org_id, me_obj['id']),
            headers=auth_headers(token)
        )

        # It should have succeeded
        self.assert200(res)

        # Assert that the object returned is the same as /me.
        moderator_obj = json.loads(res.get_data().decode())
        self.assertEqual(me_obj['id'],           moderator_obj['id'])
        self.assertEqual(me_obj['first_name'],   moderator_obj['first_name'])
        self.assertEqual(me_obj['last_name'],    moderator_obj['last_name'])
        self.assertEqual(me_obj['email'],        moderator_obj['email'])
        self.assertEqual(me_obj['participates'], moderator_obj['participates'])
        self.assertEqual(me_obj['moderates'],    moderator_obj['moderates'])
