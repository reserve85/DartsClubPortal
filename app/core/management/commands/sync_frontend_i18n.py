"""Collect every t("...") of the React frontend into app/core/frontend_i18n.py.

The frontend gets its strings translated by Django (shared prop ``i18n``),
so German stays in ONE catalog (locale/de/LC_MESSAGES/django.po).
"""

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

PATTERN = re.compile(r"""\bt\(\s*(["'`])((?:\.|(?!\1).)*)\1""", re.DOTALL)
# Plurals: tn("one", "many", n) -> both msgids.
PATTERN_TN = re.compile(r'\btn\(\s*"((?:\\.|[^"])*)"\s*,\s*"((?:\\.|[^"])*)"')


def collect() -> list[str]:
    root = Path(settings.BASE_DIR) / "frontend" / "src"
    found = set()
    for path in root.rglob("*.ts*"):
        source = path.read_text(encoding="utf-8")
        texts = [text for _quote, text in PATTERN.findall(source)]
        texts += [text for pair in PATTERN_TN.findall(source) for text in pair]
        for text in texts:
            found.add(text.replace("'", "'").replace('\\"', '"'))
    return sorted(found)


def render(msgids: list[str]) -> str:
    body = "\n".join(f"    {json.dumps(m, ensure_ascii=False)}," for m in msgids)
    return (
        '"""Msgids used by the React frontend (generated: manage.py sync_frontend_i18n)."""\n\n'
        f"MSGIDS: list[str] = [\n{body}\n]\n"
    )


class Command(BaseCommand):
    help = "Regenerate app/core/frontend_i18n.py from the frontend sources."

    def handle(self, *args, **opts):
        msgids = collect()
        target = Path(settings.BASE_DIR) / "app" / "core" / "frontend_i18n.py"
        target.write_text(render(msgids), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{len(msgids)} frontend msgids written."))
