# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import getpass
import bcrypt
import inpassing
from inpassing.models import db, Org, User, Pass, RequestLog, BorrowLogEntry

from flask_script import Manager

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

if __name__ == "__main__":
    manager.run()
