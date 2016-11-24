# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask_sqlalchemy import SQLAlchemy
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

    # Rules as a JSON object (stored as a string).
    parking_rules = db.Column(db.Text)

    ## Relationships
    # An org has a finite set of day states.
    parking_states = db.relationship('DayState', backref='org')

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

# Day states make up the finite set that any given day will be assigned to. For
# example, in an A-B system, there will be two states, one for A and one for B.
# The IDs will probably be 0 and 1 while the string fields would be A and B,
# respectively.
class DayState(db.Model):
    __tablename__ = 'daystates'

    # A day state has an id,
    id = db.Column(db.Integer, primary_key=True)
    # an organization that it is relevant belongs to,
    org_id = db.Column(db.Integer, db.ForeignKey('orgs.id'))
    # and a string representation.
    string = db.Column(db.String(50))

class User(db.Model):
    __tablename__ = 'users'

    ## Fields

    # User ID
    id = db.Column(db.Integer, primary_key=True)

    # User information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(200))
    email = db.Column(db.String(255))
    password = db.Column(db.String(255))

    # Relationship with organizations
    participates = db.relationship('Org', secondary='org_participants',
                                   back_populates='participants')

    moderates = db.relationship('Org', secondary='org_mods',
                                back_populates='mods')

    # Passes owned by this user
    passes = db.relationship('Pass', backref='owner',
                             foreign_keys='Pass.owner_id')

class Pass(db.Model):
    __tablename__ = 'passes'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('orgs.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    state_id = db.Column(db.Integer, db.ForeignKey('daystates.id'))
    spot_num = db.Column(db.Integer)

    # A pass has a given history of borrows and returns, etc.
    borrow_log = db.relationship('BorrowLogEntry', lazy='dynamic')

# A user must request a pass state and ID from a moderator of an org
class RequestLog(db.Model):
    __tablename__ = 'requestlog'

    entry_id     = db.Column(db.Integer, primary_key=True)
    org_id       = db.Column(db.Integer, db.ForeignKey('orgs.id'))
    requestor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    request_time = db.Column(db.DateTime)

    state_id = db.Column(db.Integer, db.ForeignKey('daystates.id'))
    spot_num = db.Column(db.Integer)

    assigned_pass_id = db.Column(db.Boolean)
    assignment_time =  db.Column(db.DateTime)

# Borrows record the time and to whom a pass was lent to. This will mainly be
# used to prevent some people from getting the pass all the time. The answer to
# the question "who's allowed to park with this pass *now*?" can be found in the
# Pass table.
class BorrowLogEntry(db.Model):
    __tablename__ = 'borrowlog'

    entry_id = db.Column(db.Integer, primary_key=True)
    # This is the owner of the pass as of the borrow occurring, it may not
    # reflect the current value of the passes owner.
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # We need the pass to
    pass_id = db.Column(db.Integer, db.ForeignKey('passes.id'))

    # Who it was lent to and when. If this is null we are reseting the lentee.
    lent_to = db.Column(db.Integer, db.ForeignKey('users.id'))

    # The time at which this entry was made.
    time_lent = db.Column(db.DateTime)
