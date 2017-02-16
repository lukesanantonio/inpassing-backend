# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import Blueprint, render_template

admin_www = Blueprint('admin', __name__, template_folder='templates_admin')

@admin_www.route('/')
def index():
    return render_template('index.html')

@admin_www.route('/login')
def login():
    return render_template('login.html')
