# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import unittest
from datetime import timedelta, datetime
from ..worker.daystate import current_state, num_periods


class TestDaystateSchedule(unittest.TestCase):
    def test_current_state(self):
        self.assertEqual(current_state(['A', 'B'], 0, 0), 'A')
        self.assertEqual(current_state(['A', 'B'], 0, 1), 'B')
        self.assertEqual(current_state(['A', 'B'], 0, 2), 'A')
        self.assertEqual(current_state(['A', 'B'], 0, 3), 'B')
        self.assertEqual(current_state(['A', 'B'], 0, 4), 'A')

        self.assertEqual(current_state(['A', 'B'], 1, 0), 'B')
        self.assertEqual(current_state(['A', 'B'], 1, 1), 'A')
        self.assertEqual(current_state(['A', 'B'], 1, 2), 'B')
        self.assertEqual(current_state(['A', 'B'], 1, 3), 'A')
        self.assertEqual(current_state(['A', 'B'], 1, 4), 'B')

        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 0), 'A')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 1), 'B')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 2), 'C')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 3), 'D')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 4), 'A')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 5), 'B')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 6), 'C')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 7), 'D')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 8), 'A')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 9), 'B')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 10), 'C')
        self.assertEqual(current_state(['A', 'B', 'C', 'D'], 0, 11), 'D')

    def test_num_periods(self):
        now = datetime.now()
        self.assertAlmostEqual(num_periods(timedelta(days=1), now, now), 0.0)

        self.assertAlmostEqual(num_periods(
            timedelta(days=1), now, now + timedelta(days=1)
        ), 1.0)

        self.assertAlmostEqual(num_periods(
            timedelta(days=1), now, now + timedelta(days=2)
        ), 2.0)

        self.assertAlmostEqual(num_periods(
            timedelta(days=1), now, now + timedelta(days=3)
        ), 3.0)

        self.assertAlmostEqual(num_periods(
            timedelta.max, now, now + timedelta(days=1)
        ), 0.0)

        self.assertAlmostEqual(num_periods(
            timedelta(seconds=3600), now, now + timedelta(days=1)
        ), 24.0)
