# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_, or_
from .models import Pass, db

from datetime import date, timedelta

from .util import range_inclusive_dates
from .worker.queue_util import (consumer_queue, producer_queue, user_borrow_set,
                               user_lend_set, user_borrow, user_lend)

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

def borrow_pass(r, org_id, user, date):
    """Adds the user to a single pass request queue."""

    # Use the org and date to find the consumer queue
    queue_name = consumer_queue(org_id, queue_date)

    # Add this day queue to the set of queues this user has a request in.
    # Since a user may have different passes related to different orgs, we
    # need to include both org id and user id in the key.

    # ===
    # @Bug Possible race condition after sadd but before rpush. If we add
    # the queue name to the set as if it has a request, another client (ie
    # the worker) may furfill the request and query the set to find out each
    # list where it must update the user transfer id, but the list doesn't
    # have it. If we using a LREM and RPUSH the remove would fail but it
    # would be pushed twice, once by that client and once by us.
    # ===
    borrow_set = user_borrow_set(org_id, user.id)
    num_added = r.sadd(borrow_set, queue_name)

    if num_added == 1:
        # We haven't previously added our user to this particular queue. Put
        # it at the end of the queue, in this case we push at the right and
        # pop from the left, making the head element the first in the queue.
        r.rpush(queue_name, user_borrow(user.id, user.transfer_token))
    elif num_added != 0:
        # The hell?!
        pass

def lend_pass(r, pass_obj, date):
    # What queue are we lending on?
    queue_name = producer_queue(pass_obj.org_id, date)

    # Add it to the lends of this user.
    lend_set = user_lend_set(pass_obj.org_id, pass_obj.owner_id)
    num_added = r.sadd(lend_set, queue_name)
    if num_added == 1:
        # We need to add this pass lend to the queue itself.
        r.rpush(queue_name, user_lend(pass_obj.id, pass_obj.transfer_token))

    elif num_added != 0:
        # wtf?
        pass

def borrow_pass(r, org_id, user, start_date, end_date):
    """Adds the user to each request queue in a given inclusive date range."""
    for cur_date in range_inclusive_dates(start_date, end_date):
        # ===
        # @Optimization We may want to add the user to every queue in one go.
        # ===
        borrow_pass(r, org_id, user, cur_date)

def lend_pass(r, pass_obj, start_date, end_date):
    for cur_date in range_inclusive_dates(start_date, end_date):
        # @Optimization See above
        lend_pass(r, pass_obj, cur_date)

def distribute_passes(users):
    """Distribute / lend passes to new users with a fancy magic algorithm.

    = Proposed algorithm
    1. First come, first serve.

    = Stupid Ideas

    1. Distribute a pass to a random (seeking) individual at a random time after
    the pass goes up for grabs.
    2. Give Luke the pass. *Always*.

    = Smart Ideas

    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    $ 1. Users pay for each pass where price scales with the score         $
    $ detailed above.                                                      $
    $ 2. Have users play that gambling game where you drop a ball on pegs  $
    $ and it randomly goes left or right until the bottom. The ball in the $
    $ center hole gets the pass. Each ball costs the user one ad viewing.  $
    $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

    """
