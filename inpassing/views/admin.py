# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask import Blueprint, render_template, request, redirect
from ..models import User
from ..forms import LoginForm

admin_www = Blueprint('admin', __name__, template_folder='templates_admin')

@admin_www.route('/')
def index():
    return render_template('index.html')


@admin_www.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        return redirect('/')
    return render_template('login.html', form=form)
