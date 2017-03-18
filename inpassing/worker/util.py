# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

from datetime import datetime, timezone

DATE_FMT = '%Y-%m-%d'


def date_to_str(day):
    return day.strftime(DATE_FMT)


def str_to_date(s):
    return datetime.strptime(s, DATE_FMT).replace(tzinfo=timezone.utc)
