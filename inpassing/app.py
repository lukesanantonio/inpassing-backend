# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import os
from flask import Flask

app = Flask(__name__)

# Load the config
from . import config

# Configure the app
app.config.from_object(config)

# Override config, use for production or private debug.
if 'IN_PASSING_CONFIG' in os.environ:
    app.config.from_envvar('IN_PASSING_CONFIG')
