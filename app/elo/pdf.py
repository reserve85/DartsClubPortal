"""Ranking PDF (ReportLab), A4 portrait - same columns as the ranking table."""

from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _


def _fmt_change(value: float) -> str:
    return f"{'+' if value > 0 else ''}{value:.1f}"


def _fmt_pos(value) -> str:
    return "-" if not value else f"{value:+d}"


def ranking_pdf(ranking) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11)
    story = [
        Paragraph(escape(f"{settings.SITE_NAME} - {_('Elo ranking')}"), styles["Title"]),
        Paragraph(
            escape(
                f"{ranking.from_date:%d.%m.%Y} - {ranking.to_date:%d.%m.%Y} · "
                f"{_('created')} {timezone.localtime():%d.%m.%Y %H:%M}"
            ),
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]
    rows = [["#", _("Player"), "Elo", "+/-", _("Pos."), _("Matches"), "180", "HF"]]
    for e in ranking.entries:
        name = escape(e.name)
        if e.disabled:
            name = f"<strike>{name}</strike>"
        if e.inactive:
            name += f' <font color="#6c757d">({escape(_("inactive"))})</font>'
        rows.append(
            [
                str(e.position),
                Paragraph(name, cell),
                f"{e.elo:.0f}",
                _fmt_change(e.elo_change),
                _fmt_pos(e.position_change),
                str(e.matches or "-"),
                str(e.total_180s or "-"),
                str(e.best_high_finish or "-"),
            ]
        )
    widths = [12 * mm, 62 * mm, 20 * mm, 20 * mm, 16 * mm, 18 * mm, 16 * mm, 16 * mm]
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#206bc4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buf.getvalue()
