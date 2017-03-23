# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from functools import wraps

import pytz
from flask import request, redirect, url_for, current_app
from flask_jwt_extended import utils
from flask_jwt_extended.exceptions import NoAuthorizationError, WrongTokenError
from flask_jwt_extended.utils import ctx_stack
from flask_wtf import FlaskForm
from wtforms import HiddenField

def jwt_optional(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Decode token in header
        try:
            jwt_data = utils._decode_jwt_from_request(type='access')
            # Verify this is an access token
            if jwt_data['type'] != 'access':
                raise WrongTokenError('Only access tokens can access this endpoint')

            # Check if this is a revoked token
            if utils.get_blacklist_enabled():
                utils.check_if_token_revoked(jwt_data)

            # Add the data to the context
            ctx_stack.top.jwt_identity = jwt_data['identity']
            ctx_stack.top.jwt_user_claims = jwt_data['user_claims']
        except NoAuthorizationError:
            # Ignore a missing header
            pass
        finally:
            return fn(*args, **kwargs)

    return wrapper


def range_inclusive_dates(start, end):
    date_range = end - start
    for day_i in range(date_range.days + 1):
        yield start + timedelta(days=day_i)


# Shamelessly stolen from http://flask.pocoo.org/snippets/63/
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    # @Production: Only allow https
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc


def get_redirect_target():
    # Don't bother with the referrer for now
    target = request.args.get('next')
    return target if is_safe_url(target) else None


class RedirectForm(FlaskForm):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = get_redirect_target()

    def redirect(self, endpoint='index', **values):
        if self.next.data and self.next.data != '':
            if is_safe_url(self.next.data):
                return redirect(self.next.data)
        target = get_redirect_target()
        return redirect(target or url_for(endpoint, **values))


def daystate_dict(daystate):
    return {
        'id': daystate.id,
        'org_id': daystate.org_id,
        'identifier': daystate.identifier,
        'greeting': daystate.greeting
    }


def user_dict(user):
    return {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'participates': [{'id': org.id, 'name': org.name}
                         for org in user.participates],
        'moderates': [{'id': org.id, 'name': org.name}
                      for org in user.moderates]
    }


def pass_dict(p):
    return {
        'id': p.id,
        'org_id': p.org_id,
        'owner_id': p.owner_id,
        'request_time': p.request_time,
        'requested_state_id': p.requested_state_id,
        'requested_spot_num': p.requested_spot_num,
        'assigned_time': p.assigned_time,
        'assigned_state_id': p.assigned_state_id,
        'assigned_spot_num': p.assigned_spot_num,
    }


def get_redis():
    if 'redis' in current_app.extensions:
        return current_app['redis']
    else:
        return None


SECONDS_PER_DAY = 60 * 60 * 24


def get_today_datetime(tz):
    # Use the timezone local to the org.
    day = datetime.now(pytz.utc).astimezone(tz)

    # Truncate to the nearest day and remain in the org's timezone.
    return tz.localize(datetime(day.year, day.month, day.day))


def datetime_from_timestamp(ts, tz):
    return datetime.fromtimestamp(ts, pytz.utc).astimezone(tz)
