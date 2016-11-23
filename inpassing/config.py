# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import os
SECRET_KEY=os.getenv('INPASSING_SECRET_KEY')

SQLALCHEMY_DATABASE_URI='sqlite:///db.sqlite3'
SQLALCHEMY_TRACK_MODIFICATIONS=False
