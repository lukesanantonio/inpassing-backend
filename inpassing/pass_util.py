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
