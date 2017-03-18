# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

from ..worker import rules
import unittest
from datetime import date


class TestRules(unittest.TestCase):
    def testPatternMatching(self):
        # Test it working
        self.assertTrue(rules.pattern_matches_date(
            'monday', date(2017, 3, 13))
        )
        self.assertTrue(rules.pattern_matches_date(
            'tuesday', date(2017, 3, 14))
        )
        self.assertTrue(rules.pattern_matches_date(
            'wednesday', date(2017, 3, 1))
        )
        self.assertTrue(rules.pattern_matches_date(
            'thursday', date(2017, 1, 12))
        )
        self.assertTrue(rules.pattern_matches_date(
            'friday', date(2017, 1, 20))
        )
        self.assertTrue(rules.pattern_matches_date(
            'saturday', date(2017, 1, 28))
        )
        self.assertTrue(rules.pattern_matches_date(
            'sunday', date(2017, 2, 5))
        )

        # Test it failing
        self.assertFalse(rules.pattern_matches_date(
            'monday', date(2017, 1, 1))
        )
        self.assertFalse(rules.pattern_matches_date(
            'sunday', date(2017, 1, 2))
        )

    def testPatternReoccurs(self):
        self.assertTrue(rules.pattern_reoccurs('monday'))
        self.assertTrue(rules.pattern_reoccurs('tuesday'))
        self.assertTrue(rules.pattern_reoccurs('wednesday'))
        self.assertTrue(rules.pattern_reoccurs('thursday'))
        self.assertTrue(rules.pattern_reoccurs('friday'))
        self.assertTrue(rules.pattern_reoccurs('saturday'))
        self.assertTrue(rules.pattern_reoccurs('sunday'))

        self.assertFalse(rules.pattern_reoccurs('2018-3-12'))
        self.assertFalse(rules.pattern_reoccurs('2017-1-10'))
        self.assertFalse(rules.pattern_reoccurs('2011-12-1'))
        self.assertFalse(rules.pattern_reoccurs('hello, sailor'))
