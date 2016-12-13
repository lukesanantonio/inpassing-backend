# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from functools import wraps
from flask_jwt_extended import utils
from flask_jwt_extended.utils import ctx_stack
from flask_jwt_extended.exceptions import NoAuthorizationError

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
        yield start + timedelta(days=(start + day_i))
