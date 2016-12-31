# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import sys

import redis

from inpassing.worker import ParkingWorker

if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('usage: {} <org_id>'.format(sys.argv[0]))
        exit(1)

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    worker = ParkingWorker(r, int(sys.argv[1]))
    worker.run()
