# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from . import exceptions as ex
from . import models
from .models import db, User, Org, Daystate


def user_is_participant(user_id, org_id):
    q = db.session.query(models.org_participants).filter_by(
        participant=user_id, org=org_id
    )
    (ret,) = db.session.query(q.exists()).first()
    return ret


def user_is_mod(user_id, org_id):
    q = db.session.query(models.org_mods).filter_by(mod=user_id, org=org_id)
    (ret,) = db.session.query(q.exists()).first()
    return ret


NO_DEFAULT_FIELD_VALUE = {}

def get_field(request, field, default=NO_DEFAULT_FIELD_VALUE):
    val = request.get_json().get(field, default)
    if val is NO_DEFAULT_FIELD_VALUE:
        raise ex.MissingFieldError(field)
    return val


def get_org_by_id(org_id):
    org = Org.query.filter_by(id=org_id).first()
    if org is None:
        raise ex.OrgNotFound(org_id)
    return org


def get_user_by_id(user_id):
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        raise ex.UserNotFound(user_id)
    return user


def daystate_exists(daystate_id, org_id):
    query = Daystate.query.filter_by(id=daystate_id, org_id=org_id)
    (ret,) = db.session.query(query.exists()).first()
    return ret


def verify_user_is_participant_or_mod(user_id, org_id):
    if not (user_is_participant(user_id, org_id) or
                user_is_mod(user_id, org_id)):
        raise ex.Forbidden(
            'user {} must mod or participate in org {}'.format(
                user_id, org_id
            )
        )


def verify_user_is_mod(user_id, org_id):
    if not user_is_mod(user_id, org_id):
        raise ex.Forbidden(
            'user {} must be a moderator of org {}'.format(
                user_id, org_id
            )
        )
