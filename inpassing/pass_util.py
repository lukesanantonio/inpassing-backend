# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_, or_
from .models import Pass, db

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

def distribute_passes(users):
    """Distribute / lend passes to new users with a fancy magic algorithm.

    = Proposed algorithm
    1. For each user, weight the time since their last borrow and how many
    borrows overall to form their score.
    2. Sort users by score.
    3. Give pass to the user with the highest score.
    4. ???
    5. Profit

    = Stupid Ideas

    1. First come, first serve.
    2. Distribute a pass to a random (seeking) individual at a random time after
    the pass goes up for grabs.
    3. Give Luke the pass. *Always*.

    = Smart Ideas

    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    $ 1. Users pay for each pass where price scales with the score         $
    $ detailed above.                                                      $
    $ 2. Have users play that gambling game where you drop a ball on pegs  $
    $ and it randomly goes left or right until the bottom. The ball in the $
    $ center hole gets the pass. Each ball costs the user one ad viewing.  $
    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

    """
