# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

import pytz
from datetime import datetime

SECONDS_PER_DAY = 60 * 60 * 24


def get_today_datetime(tz):
    # Use the timezone local to the org.
    day = datetime.now(pytz.utc).astimezone(tz)

    # Truncate to the nearest day and remain in the org's timezone.
    return tz.localize(datetime(day.year, day.month, day.day))


def datetime_from_timestamp(ts, tz):
    return datetime.fromtimestamp(ts, pytz.utc).astimezone(tz)


DATE_FMT = '%Y-%m-%d'


def date_to_str(day):
    return day.strftime(DATE_FMT)


def str_to_date(s, tz=None):
    ret = datetime.strptime(s, DATE_FMT)
    if tz:
        return tz.localize(ret)
    else:
        return ret


def get_day_after(ts):
    return ts.timestamp() + SECONDS_PER_DAY


class LocalizedDateUtil:
    def __init__(self, tz):
        self.tz = tz

    def today(self):
        return get_today_datetime(self.tz)

    def date_from_string(self, str):
        return str_to_date(str, self.tz)
