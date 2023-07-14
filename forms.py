from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length


class UserAddForm(FlaskForm):
    """Form for adding users."""

    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    username = StringField('Username (Must be your Spotify Username)', validators=[DataRequired()])
    password = PasswordField('Password', validators=[Length(min=6)])


class LoginForm(FlaskForm):
    """Login form."""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[Length(min=6)])


class UserEditForm(FlaskForm):
    """Edit user info"""
    
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Length(min=6)])

    
class UserSavedDashboardForm(FlaskForm):
    """User form to save the custom dashboard they created from the dash app."""
    
    dash_name = StringField('Dashboard Name', validators=[DataRequired()])
    kpi_1 = StringField('KPI 1', validators=[DataRequired()])
    kpi_2 = StringField('KPI 2', validators=[DataRequired()])
    kpi_3 = StringField('KPI 3', validators=[DataRequired()])
    kpi_4 = StringField('KPI 4', validators=[DataRequired()])
    viz_1 = StringField('Viz 1', validators=[DataRequired()])
    viz_2 = StringField('Viz 2', validators=[DataRequired()])
    viz_3 = StringField('Viz 3', validators=[DataRequired()])
    viz_4 = StringField('Viz 4', validators=[DataRequired()])
    