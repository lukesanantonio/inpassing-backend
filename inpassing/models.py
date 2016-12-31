# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

from .app import app

db = SQLAlchemy(app)

# Org: Parking rules
# Participant: A user who parks
# Moderator: A user who moderates participants of an org

# Users can participate in any number of orgs.
org_participants = db.Table('org_participants',
                            db.Column('org', db.ForeignKey('orgs.id'),
                                      primary_key=True),
                            db.Column('participant', db.ForeignKey('users.id'),
                                      primary_key=True)
)

# Users can moderate any number of orgs (and don't necessarily have to
# participate).
org_mods = db.Table('org_mods',
                    db.Column('org', db.ForeignKey('orgs.id'),
                              primary_key=True),
                    db.Column('mod', db.ForeignKey('users.id'),
                              primary_key=True)
)

class Org(db.Model):
    __tablename__ = 'orgs'

    ## Fields

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))

    # Format string to present to users informing them of the day state.
    # For example: "Today is an {} day" where state strings are A or B. The {}
    # may not be the final implementation of formatting."
    day_state_greeting_fmt = db.Column(db.String(255))

    ###
    # Idea: Put parking rules and manual overrides of the day state in redis and
    # set the overrides to expire after a while
    ###

    # Rules as a JSON object (stored as a string).
    parking_rules = db.Column(db.Text)

    ## Relationships
    # An org has a finite set of day states.
    parking_states = db.relationship('Daystate', backref='org')

    # Orgs have participants, but don't load them all at once.
    participants = db.relationship('User',
                                   secondary='org_participants',
                                   back_populates='participates',
                                   lazy='dynamic')

    # Same as above.
    mods = db.relationship('User',
                           secondary='org_mods',
                           back_populates='moderates',
                           lazy='dynamic')

    passes = db.relationship('Pass', backref='org', lazy='dynamic')

# Day states make up the finite set that any given day will be assigned to. For
# example, in an A-B system, there will be two states, one for A and one for B.
# The IDs will probably be 0 and 1 while the string fields would be A and B,
# respectively.
class Daystate(db.Model):
    __tablename__ = 'daystates'

    # A day state has an id,
    id = db.Column(db.Integer, primary_key=True)
    # an organization that it is relevant belongs to,
    org_id = db.Column(db.Integer, db.ForeignKey('orgs.id'))
    # a short string representation,
    identifier = db.Column(db.String(50))
    # and a long one.
    greeting = db.Column(db.String(200))

class User(db.Model):
    __tablename__ = 'users'

    ## Fields

    # User ID
    id = db.Column(db.Integer, primary_key=True)

    # User information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(200))
    email = db.Column(db.String(255))
    password = db.Column(db.LargeBinary(60))

    transfer_token = db.Column(db.Integer, default=0)

    # Relationship with organizations
    participates = db.relationship('Org', secondary='org_participants',
                                   back_populates='participants')

    moderates = db.relationship('Org', secondary='org_mods',
                                back_populates='mods')

    # Passes owned by this user
    passes = db.relationship('Pass', backref='owner',
                             foreign_keys='Pass.owner_id',
                             lazy='dynamic')

class Pass(db.Model):
    __tablename__ = 'passes'

    id = db.Column(db.Integer, primary_key=True)

    # This stuff should match the values in the original pass request.
    org_id = db.Column(db.Integer, db.ForeignKey('orgs.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # This is what was requested from the user
    requested_state_id = db.Column(db.Integer, db.ForeignKey('daystates.id'))
    requested_spot_num = db.Column(db.Integer)

    request_time = db.Column(db.DateTime)

    # This is the spot they were assigned
    assigned_state_id = db.Column(db.Integer, db.ForeignKey('daystates.id'))
    assigned_spot_num = db.Column(db.Integer)

    assigner = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_time = db.Column(db.DateTime)

    transfer_token = db.Column(db.Integer, default=0)

# The transfer log records the time and to whom a pass was lent to. This will
# mainly be used for logging purposes.
class Transfer(db.Model):
    __tablename__ = 'transferlog'

    id = db.Column(db.Integer, primary_key=True)

    # The pass in question. The owner is the only one who should be able to lend
    # it, even if someone else is using it. Just a reminder ;)
    pass_id = db.Column(db.Integer, db.ForeignKey('passes.id'))

    # The time that the pass was made available for transfer.
    time_requested = db.Column(db.DateTime)

    taken_from = db.Column(db.Integer, db.ForeignKey('users.id'))
    given_to = db.Column(db.Integer, db.ForeignKey('users.id'))

    # The time at which the pass was transfered.
    time_lent = db.Column(db.DateTime)

    # When will it go back to the original person?
    time_expires = db.Column(db.DateTime)
