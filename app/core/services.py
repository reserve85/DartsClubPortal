"""Audit services — the only place that writes AuditLog rows."""

import logging

from app.core.models import AuditAction, AuditLog

logger = logging.getLogger("app.core")


def log_action(action, *, user=None, target=None, metadata=None) -> AuditLog:
    """Create an audit entry for a user-initiated state change.

    ``target`` may be any model instance; ``target_type``/``target_id`` are
    derived from ``type(obj).__name__`` and ``obj.pk``.
    """
    entry = AuditLog(action=action, user=user, metadata=metadata or {})
    if target is not None:
        entry.target_type = type(target).__name__
        entry.target_id = target.pk
    entry.save()
    return entry


def _shown(field, value) -> str:
    """A form value as readable text for the audit log."""
    from datetime import date, datetime, time

    from django import forms

    if value in (None, "", [], ()):
        return "–"
    if isinstance(field, forms.ModelMultipleChoiceField):
        items = list(value)
        if items and not hasattr(items[0], "pk"):
            items = list(field.queryset.filter(pk__in=items))
        return ", ".join(sorted(str(i) for i in items)) or "–"
    if isinstance(field, forms.ModelChoiceField) and not hasattr(value, "pk"):
        value = field.queryset.filter(pk=value).first() or value
    if isinstance(field, forms.TypedChoiceField | forms.ChoiceField) and not isinstance(
        field, forms.ModelChoiceField
    ):
        value = dict(field.choices).get(value, dict(field.choices).get(str(value), value))
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)[:200]


def form_changes(form) -> list[str]:
    """What an edit form changed, as "Label: old → new" lines for the audit log.

    Password fields are never written; ``form.change_labels`` may rename fields
    (e.g. one nuLiga link per team).
    """
    labels = getattr(form, "change_labels", {})
    out = []
    for name in form.changed_data:
        if "password" in name:
            continue
        field = form.fields[name]
        old = form.initial.get(name, field.initial)
        if callable(old):
            old = old()
        new = form.cleaned_data.get(name)
        before, after = _shown(field, old), _shown(field, new)
        if before == after:
            continue
        label = labels.get(name) or str(field.label or name)
        out.append(f"{label}: {before} → {after}")
    return out


def log_email_outcome(
    *,
    success: bool,
    recipients,
    template: str,
    subject: str,
    bcc=None,
    language: str | None = None,
    error: str | None = None,
) -> None:
    """Best-effort ``EMAIL_SENT``/``EMAIL_FAILED`` audit row for one e-mail.

    Mirrors the project rule "mail problems never break business
    transactions": a failing audit write is only logged — it can never raise
    into the delivery path. Email rows carry ``user=None`` (the actor is not
    threaded through the async mail service); the addresses live in the
    metadata instead.
    """
    recipients = [str(address) for address in (recipients or [])]
    metadata = {
        "success": bool(success),
        "recipients": recipients,
        "recipient_count": len(recipients),
        "bcc": [str(address) for address in (bcc or [])],
        "template": template,
        "subject": str(subject),
        "language": language,
    }
    if error is not None:
        metadata["error"] = str(error)
    try:
        log_action(
            AuditAction.EMAIL_SENT if success else AuditAction.EMAIL_FAILED,
            user=None,
            metadata=metadata,
        )
    except Exception:  # pragma: no cover — defensive: audit must never break mail
        logger.warning("E-mail audit write failed (%s to %s).", template, recipients, exc_info=True)
