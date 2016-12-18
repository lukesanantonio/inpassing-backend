# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from datetime import datetime, timedelta
from . import queue

from .queue import LiveOrg, DATE_FMT, str_to_date

class ParkingWorker:
    def __init__(self, redis_inst, org_id):
        self.r = redis_inst
        self.live_org = LiveOrg(redis_inst, org_id)

    def run(self):
        """Distribute / lend passes to new users with a fancy magic algorithm.

        = Proposed algorithm
        1. First come, first serve.

        = Stupid Ideas

        1. Distribute a pass to a random (seeking) individual at a random time
        after the pass goes up for grabs.
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

        date_str = self.live_org.cycle_active_queue()
        if date_str == None:
            print('No data to process')
            return

        date_str = date_str.decode('utf-8')

        date = str_to_date(date_str)

        # How far are we away from that day?
        dt = date - date.today()
        if dt.days < 0:
            # Lock in, maybe, or the queue was in the past.
            print("Processing queue from the past '{}'".format(date_str))
        elif 0 <= dt.days:
            # The queue is in the very near future!
            print("Processing queue from the future '{}'".format(date_str))
