# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask_script import Manager

import inpassing

manager = Manager(inpassing.app)

@manager.command
def create_schema():
    """Create DB schema with SQLAlchemy"""

    inpassing.db.create_all()

if __name__ == "__main__":
    manager.run()
