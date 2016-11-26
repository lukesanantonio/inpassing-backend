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

    # Borrowed passes are ones that are not owned by this user but are currently
    # being used / borrowed.
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

def distribute_passes(users):
    """Distribute / lend passes to new users with a fancy magic algorithm.

    = Proposed algorithm
    1. For each user, weight the time since their last borrow and how many
    borrows overall to form their score.
    2. Sort users by score
    3. Give pass to top user.

    = Stupid Ideas

    1. First come, first serve.
    2. Distribute a pass to a random seeking individual at a random time after
    the pass goes up for grabs.
    3. Give Luke the pass. Always.

    = Smart Ideas

    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    $ 1. Pay to for each pass. Price scales with the score detailed above. $
    $ 2. Have users play that gambling game where you drop a ball on pegs  $
    $ and it randomly goes left or right until the bottom. The ball in the $
    $ center hole gets the pass. Each ball costs the user one ad viewing.  $
    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    """
