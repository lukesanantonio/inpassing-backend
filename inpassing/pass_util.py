# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_, or_
from .models import Pass, db

from datetime import date, timedelta

from .util import range_inclusive_dates

def pass_dict(p):
    return {
        'id': p.id,
        'org_id': p.org_id,
        'owner_id': p.owner_id,
        'request_time': p.request_time,
        'requested_state_id': p.requested_state_id,
        'requested_spot_num': p.requested_spot_num,
        'assigned_time': p.assigned_time,
        'assigned_state_id': p.assigned_state_id,
        'assigned_spot_num': p.assigned_spot_num,
    }

def query_user_passes(session, user_id, verified=None):
    if verified == True:
        # Only verified passes
        return session.query(Pass).filter(
            and_(Pass.owner_id == user_id, Pass.assigned_time != None)
        ).all()
    elif verified == False:
        # Only non-verified passes
        return session.query(Pass).filter(
            and_(Pass.owner_id == user_id, Pass.assigned_time == None)
        ).all()
    else:
        # All passes
        return session.query(Pass).filter(Pass.owner_id == user_id).all()

def query_org_passes(session, org_id, verified=None):
    if verified == True:
        # Only verified passes
        return session.query(Pass).filter(
            and_(Pass.org_id == org_id, Pass.assigned_time != None)
        ).all()
    elif verified == False:
        # Only non-verified passes
        return session.query(Pass).filter(
            and_(Pass.org_id == org_id, Pass.assigned_time == None)
        ).all()
    else:
        # All passes
        return session.query(Pass).filter(Pass.org_id == org_id).all()

def get_user_passes(user_id):
    """Returns all owned, borrowed and requested passes of a user."""

    # This includes all assigned (verified) passes and pass requests.
    passes = db.session.query(Pass).filter(
        or_(Pass.owner_id == user_id)
    ).all()

    ret = []

    ret.extend([{
        'pass_id': pas.id,
        'org_id': pas.org_id,
        'owner_id': pas.owner_id,
        'request_time': pas.request_time,
        'requested_state_id': pas.requested_state_id,
        'requested_spot_num': pas.requested_spot_num,
        'assigned_time': pas.assigned_time,
        'assigned_state_id': pas.assigned_state_id,
        'assigned_spot_num': pas.assigned_spot_num,
    } for pas in passes])

    return ret

def get_org_unverified_passes(org_id):

    # This function and the one before it are basically the same thing, this one
    # does the slightly different query and removes some of the members of the
    # return data points.

    reqs = db.session.query(Pass).filter(
        and_(Pass.org_id == org_id, Pass.assigned_time == None)
    ).all()

    ret = []
    ret.extend([{
        'pass_id': p.id,
        'org_id': p.org_id,
        'owner_id': p.owner_id,
        'request_time': p.request_time,
        'requested_state_id': p.requested_state_id,
        'requested_spot_num': p.requested_spot_num,
    } for p in reqs])

    return ret
