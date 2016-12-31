import datetime
import unittest

from .. import util


class TestRangeInclusiveDates(unittest.TestCase):
    def test_range_dates(self):
        start = datetime.date(2012, 12, 5)
        end = datetime.date(2012, 12, 8)

        it = util.range_inclusive_dates(start, end)

        self.assertEqual(next(it), datetime.date(2012, 12, 5))
        self.assertEqual(next(it), datetime.date(2012, 12, 6))
        self.assertEqual(next(it), datetime.date(2012, 12, 7))
        self.assertEqual(next(it), datetime.date(2012, 12, 8))
        self.assertRaises(StopIteration, next, it)

    def test_negative_range(self):
        # We should yield no dates if the end date is before the start date.
        start = datetime.date(2015, 1, 1)
        end = datetime.date(2014, 12, 30)

        it = util.range_inclusive_dates(start, end)
        self.assertRaises(StopIteration, next, it)

    def test_single_date(self):
        day = datetime.date(2019, 5, 3)

        it = util.range_inclusive_dates(day, day)
        self.assertEqual(next(it), day)
        self.assertRaises(StopIteration, next, it)
