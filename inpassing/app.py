# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import os
from flask import Flask

app = Flask(__name__, instance_relative_config=True)

from . import default_config
app.config.from_object(default_config)

# Look for config.py in a given instance folder
app.config.from_pyfile('config.py', silent=True)

# As a last ditch effort, check the file given by the environment variable. It
# could be used in place of config.py to point to alternative configuration
# files (production and debug, for example).
app.config.from_envvar('INPASSING_CONFIG', silent=True)
