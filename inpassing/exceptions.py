# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.


class InPassingException(Exception):
    def get_code(self):
        return self.code

    def get_err(self):
        return self.err

    def get_msg(self):
        return self.msg


class OrgNotFound(InPassingException):
    code = 404
    err = 'org_not_found'

    def __init__(self, id):
        self.id = id

    def get_msg(self):
        return 'Org {} does not exist'.format(self.id)


class UserNotFound(InPassingException):
    code = 404
    err = 'user_not_found'

    def __init__(self, id):
        self.id = id

    def get_msg(self):
        return 'User {} does not exist'.format(self.id)


class MissingFieldError(InPassingException):
    code = 422
    err = 'missing_field'

    def __init__(self, field):
        self.field = field

    def get_msg(self):
        return 'missing field {}'.format(self.field)


class InvalidTimezoneError(InPassingException):
    code = 422
    err = "invalid_timezone"

    def __init__(self, tz):
        self.tz = tz

    def get_msg(self):
        return 'invalid timezone {}'.format(self.tz)


class InvalidDaystate(InPassingException):
    code = 422
    err = "invalid_daystate"

    def __init__(self, ds, org):
        self.daystate_id = ds
        self.org_id = org

    def get_msg(self):
        return 'invalid daystate {} does not exist in org {}'.format(
            self.daystate_id, self.org_id)


class UserExistsError(InPassingException):
    code = 422
    err = 'user_exists'
    msg = 'user with this email already exists'


class Forbidden(InPassingException):
    code = 403
    err = 'forbidden'

    def __init__(self, msg):
        self.msg = msg

    def get_msg(self):
        return self.msg
