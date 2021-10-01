from flask_babel import gettext as _  # type: ignore
from wtforms.fields.core import StringField
from wtforms.validators import ValidationError

from lms.lmsdb.models import User


def UniqueUsernameRequired(
    _form: 'RegisterForm', field: StringField,  # type: ignore # NOQA: F821
) -> None:
    username_exists = User.get_or_none(User.username == field.data)
    if username_exists:
        raise ValidationError(_('The username is already in use'))


def UniqueEmailRequired(
    _form: 'RegisterForm', field: StringField,  # type: ignore # NOQA: F821
) -> None:
    email_exists = User.get_or_none(User.mail_address == field.data)
    if email_exists:
        raise ValidationError(_('The email is already in use'))


def EmailNotExists(
    _form: 'ResetPassForm', field: StringField,  # type: ignore # NOQA: F821
) -> None:
    email_exists = User.get_or_none(User.mail_address == field.data)
    if not email_exists:
        raise ValidationError(_('Invalid email'))
