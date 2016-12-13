# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

def range_inclusive_dates(start, end):
    date_range = end - start
    for day_i in range(date_range.days + 1):
        yield start + timedelta(days=(start + day_i))
