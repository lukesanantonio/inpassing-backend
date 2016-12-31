# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import datetime

from fixture import DataSet


class Org(DataSet):
    class locust_valley:
        name = 'Locust Valley High School'


class Daystate(DataSet):
    class a_day:
        org_id = Org.locust_valley.ref('id')
        identifier = 'A'
        greeting = 'Today is an A day'

    class b_day:
        org_id = Org.locust_valley.ref('id')
        identifier = 'B'
        greeting = 'Today is a B day'


class User(DataSet):
    class mod:
        first_name = 'Moddy'
        last_name = 'Moderator'
        email = 'admin@madeupdomain.com'
        # This is literally 'password'
        password=b'$2b$12$tb.KU6CZmjXFkivFD3qSAeQW.V3JopcaPVzQK01IIiyejlryshcMC'

        moderates = [Org.locust_valley]

    class user:
        first_name = 'John'
        last_name = 'Smitch'
        email = 'testemail@madeupdomain.com'
        password=b'$2b$12$tb.KU6CZmjXFkivFD3qSAeQW.V3JopcaPVzQK01IIiyejlryshcMC'

        participates = [Org.locust_valley]


class Pass(DataSet):
    class user_pass:
        org_id = Org.locust_valley.ref('id')
        owner_id = User.user.ref('id')
        requested_state_id = Daystate.a_day.ref('id')
        requested_spot_num = 20
        request_time = datetime.datetime.now()
        assigned_state_id = Daystate.a_day.ref('id')
        assigned_spot_num = 40
        assigned_time = datetime.datetime.now()

    class other_pass:
        org_id = Org.locust_valley.ref('id')
        owner_id = User.user.ref('id')
        requested_state_id = Daystate.b_day.ref('id')
        requested_spot_num = 30
        request_time = datetime.datetime.now()
        assigned_state_id = None
        assigned_spot_num = None
        assigned_time = None


all_data = (Org, Daystate, User, Pass)
