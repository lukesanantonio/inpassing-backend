# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

DATE_FMT = '%Y-%m-%d'

CONSUMER_QUEUE_FMT = '{}:{}:consumer'
def consumer_queue(org_id, date):
    return CONSUMER_QUEUE_FMT.format(org_id, str(date))

PRODUCER_QUEUE_FMT = '{}:{}:producer'
def producer_queue(org_id, date):
    return PRODUCER_QUEUE_FMT.format(org_id, str(date))

USER_BORROW_SET_FMT = '{}:{}:borrows'
def user_borrow_set(org_id, user_id):
    return USER_BORROW_SET_FMT.format(org_id, user_id)

USER_LEND_SET_FMT = '{}:{}:lends'
def user_lend_set(org_id, user_id):
    return USER_LEND_SET_FMT.format(org_id, user_id)

USER_REQUEST_FMT = '{}:{}'
def user_borrow(user_id, user_token):
    return USER_REQUEST_FMT.format(user_id, user_token)

USER_LEND_FMT = '{}:{}'
def user_lend(pass_id, req_token):
    return USER_LEND_FMT.format(pass_id, req_token)
