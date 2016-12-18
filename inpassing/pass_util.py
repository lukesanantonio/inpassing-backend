# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_, or_
from .models import Pass, db

from datetime import date, timedelta

from .util import range_inclusive_dates

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
