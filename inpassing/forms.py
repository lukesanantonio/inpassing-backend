# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[validators.email()])
    password = PasswordField('Password', validators=[validators.length(6)])


class SignupForm(FlaskForm):
    first_name = StringField('First Name')
    last_name = StringField('Last Name')
    email = StringField('Email', validators=[validators.email()])
    password = PasswordField('Password', validators=[
        validators.InputRequired(),
        validators.EqualTo('confirm', 'Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')
