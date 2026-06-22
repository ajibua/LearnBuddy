from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import re

class ComplexityValidator:
    def validate(self, password, user=None):
        if not re.search(r'[a-zA-Z]', password):
            raise ValidationError(
                _("The password must contain at least one letter."),
                code='password_no_letters',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("The password must contain at least one number."),
                code='password_no_numbers',
            )
        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError(
                _("The password must contain at least one special character (e.g., !, @, #, $, etc.)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Your password must contain a mixture of letters, numbers, and special characters."
        )
