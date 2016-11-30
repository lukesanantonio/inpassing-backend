# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import getpass
import bcrypt
import datetime

import inpassing
from inpassing.models import db, Org, User, Pass

from flask_script import Manager

from sqlalchemy.sql import and_

manager = Manager(inpassing.app)

@manager.command
def create_schema():
    """Create DB schema with SQLAlchemy"""

    inpassing.db.create_all()

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
    # reqs = db.session.query(PassRequest).filter(
    #     and_(PassRequest.org_id == org.id, PassRequest.assigned_pass_id == None)
    # ).all()

    # For now, we don't know how to query passes that need to be verified by an
    # org.
    reqs = []

    if len(reqs) == 0:
        print('No pass requests need to be verified')
        return

    more_to_verify = True
    while more_to_verify:
        print('Pick one, or q to finish')

        for i, req in enumerate(reqs):
            print('\t({}) Requestor: {} <ID={}>; Pass {}:{}'.format(
                i + 1,
                req.requestor.first_name + ' ' + req.requestor.last_name,
                req.requestor_id,
                req.state_id,
                req.spot_num)
            )

        req_choice = choice('Request to verify: ', reqs)
        if req_choice == None:
            more_to_verify = False
        else:
            # This is all verified now
            reqs.remove(req_choice)

            # Make a new pass given the information from the request
            new_pass = Pass(org_id=org.id, owner_id=req_choice.requestor_id,
                            state_id=req_choice.state_id,
                            spot_num=req_choice.spot_num)

            db.session.add(new_pass)

            # Record the assigned pass and time at which it was assigned
            req_choice.assigned_pass = new_pass
            req_choice.assignment_time = datetime.datetime.now()

            db.session.commit()

            more_to_verify = len(reqs)

if __name__ == "__main__":
    manager.run()
