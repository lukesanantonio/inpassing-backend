# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

from datetime import datetime, timezone

DATE_FMT = '%Y-%m-%d'


def date_to_str(day):
    return day.strftime(DATE_FMT)


def str_to_date(s, tz=None):
    ret = datetime.strptime(s, DATE_FMT)
    if tz:
        return tz.localize(ret)
    else:
        return ret
