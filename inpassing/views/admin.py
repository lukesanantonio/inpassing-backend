# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, login_required, \
    logout_user, current_user

from inpassing.view_util import get_org_by_id
from ..models import db, User
from ..forms import LoginForm, SignupForm
from ..util import get_redirect_target

admin_www = Blueprint('admin', __name__, template_folder='templates_admin')

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id=int(user_id)).first()


@admin_www.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('.user_home'))
    return render_template('index.html')


@admin_www.route('/home', methods=['GET'])
@login_required
def user_home():
    return render_template('home.html')


@admin_www.route('/orgs/<org_id>')
@login_required
def org_view(org_id):
    org = get_org_by_id(org_id)
    return render_template(
        'org.html',
        org=org,
        non_verified_passes=[p for p in org.passes if p.assigned_time is None]
    )

@admin_www.route('/logout', methods=['GET', 'POST'])
def user_logout():
    logout_user()
    redirect_url = get_redirect_target()
    return redirect(redirect_url or url_for('.index'))


@admin_www.route('/login', methods=['GET', 'POST'])
def user_login():
    form = LoginForm()
    if form.validate_on_submit():
        # Form is validated, try to log in
        user = User.query.filter_by(email=form.email.data).first()
        in_pass = form.password.data.encode('ascii')
        if user and bcrypt.checkpw(in_pass, user.password):
            # Authenticated!
            login_user(user)

            # Redirect home or elsewhere
            return form.redirect('.user_home')
    return render_template('login.html', form=form)


@admin_www.route('/signup', methods=['GET', 'POST'])
def user_signup():
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

        login_user(new_user)

        return redirect(url_for('.user_home'))

    # TODO: Eventually this should be on a field-by-field basis.
    errors = []
    for field, errs in form.errors.items():
        errors.extend(errs)
    return render_template('signup.html', form=form, errors=errors)
