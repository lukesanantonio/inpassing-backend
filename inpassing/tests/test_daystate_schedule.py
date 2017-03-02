# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import unittest
from ..worker.daystate import current_state


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

