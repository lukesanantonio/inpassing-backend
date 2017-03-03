# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import unittest
from datetime import datetime, date
from ..worker.queue import FixedDaystate


class TestQueue(unittest.TestCase):
    def test_fixed_daystate_fromstring(self):
        # Date format is YYYY-MM-DD

        str_in = '2012-11-02:4'
        fix = FixedDaystate.fromstring(str_in)
        self.assertEqual(fix.date.year,  2012)
        self.assertEqual(fix.date.month, 11)
        self.assertEqual(fix.date.day,   2)
        self.assertEqual(fix.state_id, 4)
        self.assertEqual(str(fix), str_in)

        str_in = '2017-03-03:1'
        fix = FixedDaystate.fromstring(str_in)
        self.assertEqual(fix.date.year, 2017)
        self.assertEqual(fix.date.month, 3)
        self.assertEqual(fix.date.day, 3)
        self.assertEqual(fix.state_id, 1)
        self.assertEqual(str(fix), str_in)

    def test_fixed_daystate_equality(self):
        # Is it bad to use today's date in a test? I suppose a particularly bad
        # date could break it, but what the hell
        fix = FixedDaystate(datetime.now(), 4)
        self.assertEqual(fix, fix)

        # Parse the generated string to make sure its still retained its
        # equality.
        parsed_fix = FixedDaystate.fromstring(str(fix))
        self.assertEqual(fix, parsed_fix)

        # Change something to make sure inequality works.
        fix.date = date(year=1960, month=1, day=1)
        self.assertNotEqual(fix, parsed_fix)