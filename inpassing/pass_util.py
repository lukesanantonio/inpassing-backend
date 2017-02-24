# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from sqlalchemy.sql import and_

from .models import Pass


def query_user_passes(session, user_id, verified=None):
    if verified:
        # Only verified passes
        return session.query(Pass).filter(
            and_(Pass.owner_id == user_id, Pass.assigned_time != None)
        ).all()
    elif not verified and verified is not None:
        # Only non-verified passes
        return session.query(Pass).filter(
            and_(Pass.owner_id == user_id, Pass.assigned_time == None)
        ).all()
    else:
        # All passes
        return session.query(Pass).filter(Pass.owner_id == user_id).all()


def query_org_passes(session, org_id, verified=None):
    if verified:
        # Only verified passes
        return session.query(Pass).filter(
            and_(Pass.org_id == org_id, Pass.assigned_time != None)
        ).all()
    elif not verified and verified is not None:
        # Only non-verified passes
        return session.query(Pass).filter(
            and_(Pass.org_id == org_id, Pass.assigned_time == None)
        ).all()
    else:
        # All passes
        return session.query(Pass).filter(Pass.org_id == org_id).all()
