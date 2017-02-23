# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for
from ..models import db, User
from ..forms import LoginForm, SignupForm

admin_www = Blueprint('admin', __name__, template_folder='templates_admin')

@admin_www.route('/')
def index():
    return render_template('index.html')


@admin_www.route('/home', methods=['GET'])
def user_home():
    return render_template('home.html')


@admin_www.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        return redirect('/')
    return render_template('login.html', form=form)


@admin_www.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # TODO: Use a captcha

        # Make sure a user with that email doesn't exist already
        email = form.email.data
        existing_user = User.query.filter_by(email=email).first()
        if existing_user is not None:
            # R-r-r-rip
            return render_template('signup.html', form=form,
                                   errors=['User already exists'])

        # Make a new user
        new_user = User(first_name=form.first_name.data,
                        last_name=form.last_name.data,
                        email=email)
        new_user.password = bcrypt.hashpw(form.password.data.encode('ascii'),
                                          bcrypt.gensalt(12))

        db.session.add(new_user)
        db.session.commit()

        # TODO: Log in the user
        return redirect(url_for('.user_home'))

    errors = []
    for field, errs in form.errors.items():
        errors.extend(errs)
    return render_template('signup.html', form=form, errors=errors)
