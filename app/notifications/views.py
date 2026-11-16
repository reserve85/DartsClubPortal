"""In-app mailbox actions — delete one / delete read (POST-only).

django-notifications-hq ships a GET-based, single-row ``delete`` view and has
NO bulk "delete read" endpoint, so both destructive actions of this mailbox
are custom views: POST + CSRF (the pattern of ``penalties:payment_delete``),
never GET. ``?next=`` (POST field ``next``) is validated with
``url_has_allowed_host_and_scheme`` before redirecting.
"""

from typing import ClassVar

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from notifications.models import Notification


def _redirect_after(request, fallback_name: str):
    """Validated redirect to ``next`` (POST field) — else the fallback view."""
    next_url = request.POST.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(reverse(fallback_name))


class NotificationDeleteView(LoginRequiredMixin, View):
    """Delete ONE row of the caller's own mailbox (hard delete, POST-only).

    Scoped to ``recipient=request.user`` — deleting somebody else's row is a
    404, never a silent success. GET answers 405 (the package's GET-based
    ``delete`` view is deliberately NOT reused for destructive actions).
    """

    http_method_names: ClassVar[list] = ["post"]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, recipient=request.user, pk=pk)
        notification.delete()
        return _redirect_after(request, "notifications:all")


class NotificationDeleteReadView(LoginRequiredMixin, View):
    """Delete every READ row of the caller's mailbox — unread rows survive.

    The missing bulk counterpart of the package (review: no "delete read"
    API); never touches another user's rows (scoped through the recipient
    related manager).
    """

    http_method_names: ClassVar[list] = ["post"]

    def post(self, request):
        request.user.notifications.filter(unread=False).delete()
        return _redirect_after(request, "notifications:all")


class UnsubscribeView(View):
    """One-click unsubscribe from a single mail kind (signed link, no login)."""

    def get(self, request, token):
        from app.notifications.unsubscribe import KINDS, read_token

        user, kind = read_token(token)
        return render(
            request,
            "notifications/unsubscribe.html",
            {"valid": user is not None, "label": KINDS[kind][0] if kind else "", "done": False},
        )

    def post(self, request, token):
        from app.notifications.unsubscribe import KINDS, read_token, unsubscribe

        user, kind = read_token(token)
        if user is not None:
            unsubscribe(user, kind)
        return render(
            request,
            "notifications/unsubscribe.html",
            {"valid": user is not None, "label": KINDS[kind][0] if kind else "", "done": True},
        )


class NotificationListView(LoginRequiredMixin, View):
    """The caller's mailbox as a React page (tabs Unread / All).

    Takes over the package's list views at the same URLs (``notifications:all``
    and ``notifications:unread`` still reverse to them); mark read/unread and
    "mark all" stay the package's GET actions, deletes stay POST-only.
    """

    unread_only = False

    def get(self, request):
        from django.core.paginator import Paginator
        from django.utils import timezone
        from inertia import render as inertia_render

        mailbox = request.user.notifications.select_related("actor_content_type")
        rows = mailbox.unread() if self.unread_only else mailbox.all()
        page = Paginator(rows.order_by("-timestamp"), 25).get_page(request.GET.get("page"))
        here = request.get_full_path()

        def row(notice):
            actor = notice.actor
            review = (
                reverse("accounts:approval", args=[actor.pk])
                if getattr(actor, "approval_status", None) == "pending"
                else None
            )
            toggle = (
                "notifications:mark_as_read" if notice.unread else "notifications:mark_as_unread"
            )
            return {
                "id": notice.pk,
                "verb": notice.verb,
                "actor": str(actor) if actor else "",
                "when": timezone.localtime(notice.timestamp).isoformat(),
                "unread": notice.unread,
                "reviewUrl": review,
                "toggleUrl": f"{reverse(toggle, args=[notice.slug])}?next={here}",
                "deleteUrl": reverse("notifications_manage:delete_one", args=[notice.pk]),
            }

        props = {
            "tab": "unread" if self.unread_only else "all",
            "rows": [row(n) for n in page.object_list],
            "page": page.number,
            "pages": page.paginator.num_pages,
            "unreadCount": mailbox.unread().count(),
            "urls": {
                "all": reverse("notifications:all"),
                "unread": reverse("notifications:unread"),
                "markAll": f"{reverse('notifications:mark_all_as_read')}?next={here}",
                "deleteRead": reverse("notifications_manage:delete_read"),
            },
        }
        return inertia_render(
            request,
            "Notifications",
            props=props,
            template_data={"notifications": page.object_list, "page_obj": page},
        )
