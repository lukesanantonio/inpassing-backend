# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_, or_
from .models import Pass, PassRequest, db

def get_user_passes(user_id):
    """Returns all owned, borrowed and requested passes of a user."""

    # Find pending and successfull requests
    pending_requests = db.session.query(PassRequest).filter(
        and_(PassRequest.requestor_id == user_id,
             PassRequest.assigned_pass_id == None)
    ).all()

    successful_requests = db.session.query(PassRequest).filter(
        and_(PassRequest.requestor_id == user_id,
             PassRequest.assigned_pass_id != None)
    ).all()

    # Borrowed passes are ones that are not owned by the user and being
    # currently used. I'm not sure if Pass.owner_id will ever equal Pass.user_id
    # so we use this and to keep it safe.
    borrowed_passes = db.session.query(Pass).filter(
        and_(Pass.owner_id != user_id,
             Pass.user_id == user_id)
    ).all()

    # All non-pending passes related to this user
    passes = borrowed_passes[:]

    # Note that the request state ID and spot num can be different from
    # what was actually assigned, so we have to use the values from the assigned
    # pass object, itself.
    passes.extend([req.assigned_pass for req in successful_requests])

    ret = []
    ret.extend([{
        'pass_id': pas.id,
        'org_id': pas.org_id,
        'pending': False,
        'owned': pas.owner_id == user_id,
        'using': ((pas.owner_id == user_id and pas.user_id == None) or
                  pas.user_id == user_id),
        'state_id': pas.state_id,
        'spot_num': pas.spot_num,
    } for pas in passes])

    ret.extend([{
        'request_id': req.id,
        'org_id': req.org_id,
        'pending': True,
        'owned': False,
        'using': False,
        'request_time': req.request_time.isoformat(),
        'state_id': req.state_id,
        'spot_num': req.spot_num,
    } for req in pending_requests])

    return ret
