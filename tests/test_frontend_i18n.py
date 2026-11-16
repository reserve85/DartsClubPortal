"""The React frontend's strings: list up to date and translated to German."""

from app.core.frontend_i18n import MSGIDS
from app.core.management.commands.sync_frontend_i18n import collect
from tests.test_i18n import PO_DE, _norm, _po_msgids


def test_generated_msgid_list_is_up_to_date():
    assert collect() == MSGIDS, "run: python manage.py sync_frontend_i18n"


def test_every_frontend_string_has_a_german_translation():
    catalog = _po_msgids(PO_DE)
    missing = [m for m in MSGIDS if _norm(m) not in catalog]
    assert not missing, f"missing in locale/de/LC_MESSAGES/django.po: {missing}"
