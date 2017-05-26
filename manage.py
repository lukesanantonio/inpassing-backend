# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import datetime
import getpass

import bcrypt
from flask_script import Manager
from sqlalchemy.sql import and_

import inpassing
from inpassing.models import db, Org, User, Pass, Daystate

# Create a test app
from inpassing.views import redis_store
from inpassing.worker import LiveOrg
from inpassing.worker.queue import FixedDaystate
from inpassing.worker.rules import RuleSet

app = inpassing.create_app(instance_relative_config=True)

manager = Manager(app)


@manager.command
def create_schema():
    """Create DB schema with SQLAlchemy"""

    inpassing.db.create_all()


@manager.command
def init_test_data():

    org = Org(name='Locust Valley High School', timezone="America/New_York")
    db.session.add(org)

    db.session.commit()

    a_day = Daystate(org_id=org.id, identifier='A', greeting='Today is an A day')
    b_day = Daystate(org_id=org.id, identifier='B', greeting='Today is an B day')

    mod = User(first_name='Moddy', last_name='McModerator',
               email='admin@inpassing.com',
               password=b'$2b$12$tb.KU6CZmjXFkivFD3qSAeQW.V3JopcaPVzQK01IIiyejlryshcMC')
    org.mods.append(mod)

    user = User(first_name='John', last_name='Smitch',
                email='person@inpassing.com',
                password=b'$2b$12$tb.KU6CZmjXFkivFD3qSAeQW.V3JopcaPVzQK01IIiyejlryshcMC')
    org.participants.append(user)

    db.session.add_all([a_day, b_day, mod, user])

    db.session.commit()

    user_pass = Pass(org_id=org.id, owner_id=user.id,
                     requested_state_id=a_day.id, requested_spot_num=20,
                     request_time=datetime.datetime.now(),
                     assigned_state_id=a_day.id, assigned_spot_num=13,
                     assigned_time=datetime.datetime.now())
    db.session.add(user_pass)
    other_pass = Pass(org_id=org.id, owner_id=user.id,
                     requested_state_id=b_day.id, requested_spot_num=13,
                     request_time=datetime.datetime.now())
    db.session.add(other_pass)

    db.session.commit()

    live_org = LiveOrg(redis_store, org)

    live_org.set_state_sequence([a_day.id, b_day.id])

    live_org.push_fixed_daystate(
        FixedDaystate(datetime.datetime(2017, 4, 18), a_day.id)
    )

    live_org.push_rule_set(RuleSet('*', True, 'cur'))
    live_org.push_rule_set(RuleSet('sunday', False, 'none'))
    live_org.push_rule_set(RuleSet('saturday', False, 'none'))


def parse_field(prompt_fmt, cur_value):
    """Parse a value that can be correctly later."""

    ret = input(prompt_fmt.format(cur_value))
    if ret != '':
        return ret.strip()
    return cur_value


def is_yes(val):
    return True if val in ['y', 'Y', 'yes', 'Yes', 'YES'] else False


def choice(prompt, arr):
    """ Chooses a value from the array with a prompt, using a one-based value."""

    choice_str = input(prompt)

    try:
        choice_i = int(choice_str) - 1
    except:
        return None

    if choice_i < 0 or len(arr) <= choice_i:
        return None

    return arr[choice_i]


@manager.command
def create_user():
    """Creates a user"""

    first_name = ''
    last_name = ''
    email = ''
    password = ''

    is_correct = False
    while not is_correct:
        first_name = parse_field('First Name [{}]: ', first_name)
        last_name = parse_field('Last Name [{}]: ', last_name)
        email = parse_field('Email [{}]: ', email)

        password = getpass.getpass()

        is_correct = is_yes(input('Is this correct? '))

    new_user = User(first_name=first_name, last_name=last_name, email=email)
    new_user.password = bcrypt.hashpw(password.encode('ascii'),
                                      bcrypt.gensalt())

    inpassing.db.session.add(new_user)
    inpassing.db.session.commit()

    print('Added user {} ({})'.format(new_user.id, new_user.email))


@manager.command
def create_org():
    """Creates an organization"""

    name = ''
    is_correct = False
    while not is_correct:
        name = parse_field('Name [{}]: ', name)
        is_correct = is_yes(input('Is this correct? '))

    new_org = Org(name=name)
    db.session.add(new_org)
    db.session.commit()

    print('Added org {} ({})'.format(new_org.id, new_org.name))


@manager.command
def verify_pass():
    pat = input('Org search term: ')
    pat = '%' + pat + '%'
    orgs = db.session.query(Org).filter(Org.name.like(pat)).all()

    if len(orgs) == 0:
        print('No orgs found')
        return

    for i, org in enumerate(orgs):
        # Start at one to be slightly more user-friendly.
        print('\t({}) {} <ID={}>'.format(i + 1, org.name, org.id))

    org = choice('Org: ', orgs)
    if org == None:
        print('Invalid Org')
        return

    print('You picked {}'.format(org.name))

    # This finds all the un verified passes for this org
    reqs = db.session.query(Pass).filter(
        and_(Pass.org_id == org.id, Pass.assigned_time == None)
    ).all()

    if len(reqs) == 0:
        print('No pass requests need to be verified')
        return

    more_to_verify = True
    while more_to_verify:
        print('Pick one, or q to finish')

        for i, req in enumerate(reqs):
            print('\t({}) Requestor: {} <ID={}>; Pass {}:{}'.format(
                i + 1,
                req.owner.first_name + ' ' + req.owner.last_name,
                req.owner.id,
                req.requested_state_id,
                req.requested_spot_num)
            )

        req_choice = choice('Request to verify: ', reqs)
        if req_choice == None:
            more_to_verify = False
        else:
            # This is all verified now
            reqs.remove(req_choice)

            # Approve the request
            req_choice.assigned_state_id = req_choice.requested_state_id
            req_choice.assigned_spot_num = req_choice.requested_spot_num
            req_choice.assigned_time = datetime.datetime.now()

            db.session.commit()

            more_to_verify = len(reqs)


if __name__ == "__main__":
    manager.run()
