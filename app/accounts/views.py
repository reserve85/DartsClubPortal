"""Account views — admin user management, approval workflow, settings, theme.

Login/logout/password flows are provided by django-allauth (mounted in
``config/urls.py``); this module never sends e-mails itself — all
notifications go through ``app.notifications.services.notification_service``.
"""

from typing import ClassVar

from allauth.account import views as allauth_views
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView
from inertia import render as inertia_render

from app.accounts.forms import (
    EmailChangeForm,
    InvitationAcceptForm,
    InviteCreateForm,
    SettingsForm,
    UserApprovalForm,
    UserCreateForm,
    UserUpdateForm,
)
from app.accounts.models import ApprovalStatus, Invitation, User
from app.accounts.services import (
    accept_invitation,
    cancel_invitation,
    create_invitation,
    mark_emails_verified,
    match_player_for_name,
    resend_invitation,
)
from app.core.choices import ThemeChoice
from app.core.inertia_utils import InertiaFormMixin, form_errors, form_schema, request_data
from app.core.models import AuditAction
from app.core.permissions import (
    GROUP_ADMIN,
    GROUP_PLAYER,
    GroupRequiredMixin,
    user_admin_scopes,
)
from app.core.services import log_action
from app.notifications.inapp import (
    clear_approval_notifications,
    notify_approval_decided,
    notify_invitation_completed,
)
from app.notifications.services import notification_service, reschedule_pending
from app.players.models import Player


def _when(value):
    return timezone.localtime(value).isoformat() if value else None


def _page_props(context) -> dict:
    page = context.get("page_obj")
    if page is None:
        return {"page": 1, "pages": 1}
    return {"page": page.number, "pages": page.paginator.num_pages}


class UserListView(GroupRequiredMixin, LoginRequiredMixin, ListView):
    groups: ClassVar[list] = [GROUP_ADMIN]
    model = User
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        # select_related("invitation") feeds the pre-assignment columns of
        # invited rows via the safe user.pending_invitation accessor.
        return User.objects.select_related("team", "player_link", "invitation").order_by("email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_count"] = User.objects.filter(
            approval_status=ApprovalStatus.PENDING
        ).count()
        # Open requests INCLUDING expired ones — they need a resend/cancel
        # decision, so they must stay visible on the badge.
        context["invite_count"] = Invitation.objects.filter(accepted_at__isnull=True).count()
        return context

    def render_to_response(self, context, **response_kwargs):
        from app.players.avatars import avatar_url

        def row(user):
            invite = user.pending_invitation
            player = user.player_link
            invited_player = invite.player.name if invite and invite.player else ""
            invited_team = invite.team.name if invite and invite.team else ""
            requested = user.approval_status == ApprovalStatus.REQUESTED
            return {
                "id": user.pk,
                "email": user.email,
                # The linked player IS the person; the registration name only
                # stands in for accounts without a player (club account, pending).
                "name": player.name if player else (user.full_name or invited_player),
                "avatar": avatar_url(player) if player else "",
                "player": player.name if player else invited_player,
                "playerUrl": reverse("players:player_detail", args=[player.pk]) if player else None,
                "role": user.role or "",
                "adminScopes": sorted(user_admin_scopes(user)),
                "team": user.team.name if user.team else invited_team,
                "status": user.approval_status,
                "active": user.is_active,
                "lastLogin": _when(user.last_login),
                "editUrl": None if requested else reverse("accounts:user_update", args=[user.pk]),
                "reviewUrl": (
                    reverse("accounts:approval", args=[user.pk])
                    if user.approval_status == ApprovalStatus.PENDING
                    else None
                ),
                "qrUrl": (
                    reverse("accounts:user_qr", args=[user.pk])
                    if user.is_club_account and user.is_active and not requested
                    else None
                ),
            }

        props = {
            "users": [row(u) for u in context["users"]],
            "pendingCount": context["pending_count"],
            "inviteCount": context["invite_count"],
            **_page_props(context),
        }
        return inertia_render(self.request, "Admin/Users", props=props, template_data=context)


class PendingUserListView(GroupRequiredMixin, LoginRequiredMixin, ListView):
    """All self-registered accounts waiting for the admin decision."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    model = User
    context_object_name = "pending_users"

    def get_queryset(self):
        return (
            User.objects.filter(approval_status=ApprovalStatus.PENDING)
            .select_related("player_link")
            .order_by("-date_joined")
        )

    def render_to_response(self, context, **response_kwargs):
        props = {
            "users": [
                {
                    "id": u.pk,
                    "email": u.email,
                    "name": u.full_name,
                    "joined": _when(u.date_joined),
                    "reviewUrl": reverse("accounts:approval", args=[u.pk]),
                }
                for u in context["pending_users"]
            ]
        }
        return inertia_render(self.request, "Admin/Pending", props=props, template_data=context)


class UserApprovalView(GroupRequiredMixin, LoginRequiredMixin, View):
    """Review ONE pending user: approve (+ link/create player) or reject.

    Approve and player assignment happen in a SINGLE save operation — the
    admin needs exactly one click plus (optionally) the player selection.
    """

    groups: ClassVar[list] = [GROUP_ADMIN]

    def get_object(self, pk) -> User:
        return get_object_or_404(User, pk=pk)

    def get(self, request, pk):
        user = self.get_object(pk)
        # Pre-select the best-matching unlinked player for the name the user
        # entered at registration (exact -> fuzzy -> nothing). The suggestion
        # only affects the initial render — the POST validates the submitted
        # player against the form queryset as before.
        matched = match_player_for_name(user.full_name)
        initial = {"player": matched.pk} if matched is not None else {}
        return self._render(request, user, UserApprovalForm(initial=initial))

    def _render(self, request, user, form):
        props = {
            "pendingUser": {
                "id": user.pk,
                "email": user.email,
                "name": user.full_name,
                "joined": _when(user.date_joined),
            },
            "fields": form_schema(form),
            "errors": form_errors(form) if form.is_bound else {},
            "action": reverse("accounts:approval", args=[user.pk]),
            "backUrl": reverse("accounts:approval_list"),
        }
        return inertia_render(
            request,
            "Admin/Approval",
            props=props,
            template_data={"pending_user": user, "form": form},
        )

    def post(self, request, pk):
        user = self.get_object(pk)
        action = request.POST.get("action")

        if action == "reject":
            with transaction.atomic():
                user.approval_status = ApprovalStatus.REJECTED
                user.save(update_fields=["approval_status"])
                log_action(
                    AuditAction.USER_REJECTED,
                    user=request.user,
                    target=user,
                    metadata={"email": user.email},
                )
            notification_service.send_account_rejected(user=user, request=request)
            clear_approval_notifications(user)
            notify_approval_decided(user, approved=False)
            messages.success(request, _("User rejected."))
            return redirect("accounts:approval_list")

        if action != "approve":
            messages.error(request, _("Please choose an action."))
            return self._render(request, user, UserApprovalForm())

        form = UserApprovalForm(request.POST)
        if not form.is_valid():
            return self._render(request, user, form)

        player = form.cleaned_data.get("player")
        new_player_name = (form.cleaned_data.get("new_player_name") or "").strip()
        # Approval = status + optional player creation/link + role + audit —
        # one transaction, then the e-mail fires after the commit.
        with transaction.atomic():
            if new_player_name:
                player = Player.objects.create(name=new_player_name)

            # ONE save: approval status + player link (single save operation).
            user.approval_status = ApprovalStatus.APPROVED
            if player is not None:
                user.player_link = player
            user.save()

            # Approval vouches for the address: skip the extra verify-by-link wall.
            mark_emails_verified(user)

            # Freshly approved self-registered users become players unless an
            # admin already assigned a role.
            if player is not None and not user.groups.exists():
                player_group, _created = Group.objects.get_or_create(name=GROUP_PLAYER)
                user.groups.add(player_group)

            log_action(
                AuditAction.USER_APPROVED,
                user=request.user,
                target=user,
                metadata={
                    "email": user.email,
                    "player_id": player.pk if player else None,
                },
            )
        notification_service.send_account_approved(user=user, request=request)
        clear_approval_notifications(user)
        notify_approval_decided(user, approved=True)
        messages.success(request, _("User approved."))
        return redirect("accounts:approval_list")


def _account_groups(with_password: bool = False) -> list:
    """Account forms in sections: the account, role and rights, assignments."""
    groups = [
        {
            "title": str(_("Account")),
            "rows": [["email", "full_name"], ["preferred_language", "is_active"]],
        },
        {
            "title": str(_("Role and rights")),
            "rows": [
                ["role"],
                ["admin_elo", "admin_penalty", "admin_portal"],
                ["elo_access", "penalty_access"],
            ],
        },
        {"title": str(_("Assignment")), "rows": [["player_link", "team"], ["is_club_account"]]},
    ]
    if with_password:
        groups.append({"title": str(_("Password")), "rows": [["password1", "password2"]]})
    return groups


class UserCreateView(GroupRequiredMixin, LoginRequiredMixin, InertiaFormMixin, CreateView):
    groups: ClassVar[list] = [GROUP_ADMIN]
    model = User
    form_class = UserCreateForm
    success_url = reverse_lazy("accounts:user_list")

    def form_page_props(self, form):
        return {
            "title": str(_("New user")),
            "subtitle": str(
                _("Usually an invitation is the better way: the person sets the password.")
            ),
            "submitLabel": str(_("Create user")),
            "cancelUrl": reverse("accounts:user_list"),
            "groups": _account_groups(with_password=True),
        }

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(
            AuditAction.USER_CREATED,
            user=self.request.user,
            target=self.object,
            metadata={"account": self.object.email},
        )
        messages.success(self.request, _("User created."))
        return response


def _invite_guard(request, pk):
    """Block edit/deactivate of requested (invited, not yet accepted) users.

    A wrong entry is fixed with Cancel — editing here would bypass the
    invitation payload. Returns the redirect response, or ``None`` to proceed.
    """
    if User.objects.filter(pk=pk, approval_status=ApprovalStatus.REQUESTED).exists():
        messages.error(request, _("Cancel or resend the invitation instead."))
        return redirect("accounts:invite_list")
    return None


class UserUpdateView(GroupRequiredMixin, LoginRequiredMixin, InertiaFormMixin, UpdateView):
    groups: ClassVar[list] = [GROUP_ADMIN]
    model = User
    form_class = UserUpdateForm
    success_url = reverse_lazy("accounts:user_list")

    def get(self, request, *args, **kwargs):
        return _invite_guard(request, kwargs.get("pk")) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return _invite_guard(request, kwargs.get("pk")) or super().post(request, *args, **kwargs)

    def form_page_props(self, form):
        user = self.object
        # Same rule as the user list: the linked player, else the registration name.
        name = user.player_link.name if user.player_link else user.full_name
        return {
            "title": str(_("Edit user")),
            "subtitle": f"{name} · {user.email}" if name else user.email,
            "badge": name or user.email,
            "badgePerson": True,
            "submitLabel": str(_("Save changes")),
            "cancelUrl": reverse("accounts:user_list"),
            "groups": _account_groups(),
            "passwordSet": self._password_set(user),
            "notice": str(
                _(
                    "Accounts are never deleted: switch off active to lock the login. "
                    "Captain and cashier are assignments any role can hold."
                )
            ),
        }

    def _password_set(self, user):
        """The "set password" card: not for the own account, and the system
        account only when it is signed in itself (then it is the own account)."""
        if user == self.request.user or (user.is_superuser and not self.request.user.is_superuser):
            return None
        name = user.player_link.name if user.player_link else (user.full_name or user.email)
        return {
            "url": reverse("accounts:user_set_password", args=[user.pk]),
            "name": name,
            "club": bool(user.is_club_account),
        }

    def _other_admins_exist(self) -> bool:
        """True when another account could still manage users and rights."""
        from django.db.models import Q

        from app.core.permissions import user_is_portal_admin

        others = (
            User.objects.filter(Q(is_superuser=True) | Q(groups__name=GROUP_ADMIN))
            .exclude(pk=self.request.user.pk)
            .filter(is_active=True)
            .distinct()
        )
        return any(user_is_portal_admin(u) for u in others)

    def form_valid(self, form):
        # Lockout protection: an admin may edit themselves, but must not
        # accidentally remove the last Admin rights or deactivate themself.
        if form.instance.pk == self.request.user.pk:
            if not form.cleaned_data.get("is_active", True):
                form.add_error("is_active", _("You cannot deactivate your own account."))
                return self.form_invalid(form)
            if (
                (
                    form.cleaned_data.get("role") != GROUP_ADMIN
                    or not form.cleaned_data.get("admin_portal")
                )
                and not self.request.user.is_superuser
                and not self._other_admins_exist()
            ):
                form.add_error(
                    "role",
                    _("You are the only Admin. Give the Admin role to another user first."),
                )
                return self.form_invalid(form)
        from app.core.services import form_changes

        changes = form_changes(form)
        response = super().form_valid(form)
        log_action(
            AuditAction.USER_UPDATED,
            user=self.request.user,
            target=self.object,
            metadata={"account": self.object.email, "changes": changes},
        )
        messages.success(self.request, _("User updated."))
        return response


class UserSetPasswordView(GroupRequiredMixin, LoginRequiredMixin, View):
    """A portal admin gives an account a new password (no e-mail needed).

    The page asks before posting. Every session of the account ends with the
    new password (Django checks the password hash per session), and for the
    club account every printed QR code becomes invalid.
    """

    groups: ClassVar[list] = [GROUP_ADMIN]  # admin_scope "portal" (mixin default)

    def post(self, request, pk):
        from django.contrib.auth.password_validation import validate_password

        blocked = _invite_guard(request, pk)
        if blocked is not None:
            return blocked
        target = get_object_or_404(User, pk=pk)
        back = redirect("accounts:user_update", pk=pk)
        if target == request.user:
            messages.error(request, _("Change your own password under Settings."))
            return back
        if target.is_superuser and not request.user.is_superuser:
            messages.error(request, _("Only the system account may change its own password."))
            return back
        data = request_data(request)
        password1 = str(data.get("password1") or "")
        password2 = str(data.get("password2") or "")
        if not password1 or password1 != password2:
            messages.error(request, _("The two password fields didn't match."))
            return back
        try:
            validate_password(password1, user=target)
        except ValidationError as error:
            messages.error(request, " ".join(str(m) for m in error.messages))
            return back
        target.set_password(password1)
        target.save(update_fields=["password"])
        log_action(
            AuditAction.USER_UPDATED,
            user=request.user,
            target=target,
            metadata={"password": "set by an admin"},
        )
        messages.success(request, _("The new password is set."))
        return back


class ClubAccountLockMixin:
    """The shared club account must not change its own password: anybody at
    the club tablet could lock the club out. A portal admin manages it."""

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "is_club_account", False):
            messages.error(request, _("A portal admin manages the password of the club account."))
            return redirect("accounts:settings")
        return super().dispatch(request, *args, **kwargs)


class LockedPasswordChangeView(ClubAccountLockMixin, allauth_views.PasswordChangeView):
    pass


class LockedPasswordSetView(ClubAccountLockMixin, allauth_views.PasswordSetView):
    pass


class UserDeactivateView(GroupRequiredMixin, LoginRequiredMixin, View):
    groups: ClassVar[list] = [GROUP_ADMIN]

    def post(self, request, pk):
        blocked = _invite_guard(request, pk)
        if blocked is not None:
            return blocked
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, _("You cannot deactivate your own account."))
            return redirect("accounts:user_list")
        user.is_active = False
        user.save(update_fields=["is_active"])
        log_action(AuditAction.USER_DEACTIVATED, user=request.user, target=user)
        messages.success(request, _("User deactivated."))
        return redirect("accounts:user_list")


# ---------------------------------------------------------------------------
# Invitations (admin lifecycle + public acceptance)
# ---------------------------------------------------------------------------
def _invite_error_text(error: ValidationError) -> str:
    """Flatten a (possibly multi-message) ValidationError for ``messages``."""
    return " ".join(str(message) for message in error.messages)


class InviteListView(GroupRequiredMixin, LoginRequiredMixin, ListView):
    """Open/expiring/expired/accepted requests with Resend + Cancel actions."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    model = Invitation
    context_object_name = "invitations"
    paginate_by = 25

    def get_queryset(self):
        return Invitation.objects.select_related("user", "player", "team", "invited_by")

    def render_to_response(self, context, **response_kwargs):
        base = f"{self.request.scheme}://{self.request.get_host()}"

        def row(inv):
            open_ = not inv.accepted_at
            return {
                "id": inv.pk,
                "email": inv.user.email if inv.user_id else "",
                "role": str(inv.get_role_display()),
                "team": inv.team.name if inv.team_id else "",
                "player": inv.player.name if inv.player_id else "",
                "invitedBy": inv.invited_by.email if inv.invited_by_id else "",
                "created": _when(inv.created_at),
                "accepted": _when(inv.accepted_at),
                "expires": _when(inv.expires_at),
                "status": inv.status,
                "link": (
                    base + reverse("accounts:invite_accept", args=[inv.token])
                    if inv.is_open
                    else None
                ),
                "resendUrl": reverse("accounts:invite_resend", args=[inv.pk]) if open_ else None,
                "cancelUrl": reverse("accounts:invite_cancel", args=[inv.pk]) if open_ else None,
            }

        props = {"invitations": [row(i) for i in context["invitations"]], **_page_props(context)}
        return inertia_render(self.request, "Admin/Invites", props=props, template_data=context)


class InviteCreateView(GroupRequiredMixin, LoginRequiredMixin, InertiaFormMixin, FormView):
    """Send an invitation — spans two models, hence FormView (no CreateView)."""

    groups: ClassVar[list] = [GROUP_ADMIN]
    form_class = InviteCreateForm
    success_url = reverse_lazy("accounts:invite_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The form template documents the link validity (env-configurable).
        context["invite_expire_days"] = settings.INVITE_EXPIRE_DAYS
        return context

    def form_page_props(self, form):
        return {
            "title": str(_("New invitation")),
            "subtitle": str(
                _(
                    "The person gets an e-mail with a link to set the password "
                    "(valid %(days)s days)."
                )
                % {"days": settings.INVITE_EXPIRE_DAYS}
            ),
            "submitLabel": str(_("Send invitation")),
            "cancelUrl": reverse("accounts:invite_list"),
            "groups": [
                {"title": str(_("Invitation")), "rows": [["email", "preferred_language"]]},
                {
                    "title": str(_("Role and access")),
                    "rows": [["role"], ["elo_access", "penalty_access"]],
                },
                {"title": str(_("Assignment")), "rows": [["player", "team"]]},
            ],
        }

    def form_valid(self, form):
        data = form.cleaned_data
        invitation = create_invitation(
            email=data["email"],
            role=data["role"],
            team=data.get("team"),
            player=data.get("player"),
            language=data["preferred_language"],
            invited_by=self.request.user,
        )
        log_action(
            AuditAction.USER_INVITE_SENT,
            user=self.request.user,
            target=invitation.user,
            metadata={
                "email": invitation.user.email,
                "role": invitation.role,
                "player_id": invitation.player_id,
                "team_id": invitation.team_id,
            },
        )
        # Mail AFTER commit; a dead SMTP must never look like a dead request —
        # the warning points at Resend instead of failing silently.
        sent = notification_service.send_invitation(invitation, request=self.request)
        if sent == 0:
            messages.warning(
                self.request,
                _("Invitation created, but the e-mail could not be sent — use Resend."),
            )
        else:
            messages.success(self.request, _("Invitation sent."))
        return super().form_valid(form)


class InviteResendView(GroupRequiredMixin, LoginRequiredMixin, View):
    """POST-only: new token + fresh expiry, then re-send the mail."""

    groups: ClassVar[list] = [GROUP_ADMIN]

    def post(self, request, pk):
        invitation = get_object_or_404(Invitation, pk=pk)
        try:
            resend_invitation(invitation, actor=request.user)
        except ValidationError as error:
            messages.error(request, _invite_error_text(error))
            return redirect("accounts:invite_list")
        sent = notification_service.send_invitation(invitation, request=request)
        if sent == 0:
            messages.warning(
                request,
                _("Invitation created, but the e-mail could not be sent — use Resend."),
            )
        else:
            messages.success(request, _("Invitation resent."))
        return redirect("accounts:invite_list")


class InviteCancelView(GroupRequiredMixin, LoginRequiredMixin, View):
    """POST-only + confirm: hard-delete the requested user (cascade)."""

    groups: ClassVar[list] = [GROUP_ADMIN]

    def post(self, request, pk):
        invitation = get_object_or_404(Invitation, pk=pk)
        try:
            cancel_invitation(invitation, actor=request.user)
        except ValidationError as error:
            # e.g. crafted POST against an already ACCEPTED invitation —
            # refused server-side (review B3), never a 500 or a silent delete.
            messages.error(request, _invite_error_text(error))
            return redirect("accounts:invite_list")
        messages.success(request, _("Invitation cancelled — the account was deleted."))
        return redirect("accounts:invite_list")


def _invite_unusable_reason(invitation) -> str | None:
    """Why the link cannot be used right now — or ``None`` when it can.

    Same wording as the service re-checks (one msgid per message); accepted
    rows never reach this (their token is blanked → plain 404).
    """
    if invitation.accepted_at is not None:
        return str(_("This invitation has already been used."))
    if invitation.expires_at <= timezone.now():
        return str(_("This invitation has expired. Please ask the club to resend it."))
    return None


class InviteAcceptView(View):
    """Public set-password page of ``invite/<token>/`` (CSRF-protected POST).

    GET: unknown token → 404; expired → explanatory error WITHOUT the form.
    Valid POST → accept (one transaction) → audit → admin notifications →
    success message → redirect to the login page (no auto-login, consistent
    with the approval flow). No allauth ``user_signed_up`` fires here — never
    "waiting for approval", never an approval-request bell.
    """

    def _render(self, request, invitation, form=None, error=None):
        from app.accounts.entrance import entrance_response

        return entrance_response(
            request,
            "invite_accept",
            {"invitation": invitation, "form": form, "error": error},
            invitation={
                "email": invitation.user.email if invitation.user_id else "",
                "role": str(invitation.get_role_display()),
                "team": invitation.team.name if invitation.team_id else "",
                "player": invitation.player.name if invitation.player_id else "",
                "expires": _when(invitation.expires_at),
                "error": str(error) if error else None,
            },
        )

    def get(self, request, token):
        invitation = get_object_or_404(Invitation, token=token)
        if request.user.is_authenticated:
            return redirect("home")
        error = _invite_unusable_reason(invitation)
        if error is not None:
            return self._render(request, invitation, error=error)
        return self._render(request, invitation, form=InvitationAcceptForm())

    def post(self, request, token):
        invitation = get_object_or_404(Invitation, token=token)
        if request.user.is_authenticated:
            return redirect("home")
        form = InvitationAcceptForm(request.POST)
        if not form.is_valid():
            return self._render(request, invitation, form=form)
        try:
            user = accept_invitation(invitation, password=form.cleaned_data["password1"])
        except ValidationError as error:
            form.add_error(None, error)
            return self._render(request, invitation, form=form)
        log_action(
            AuditAction.USER_INVITE_ACCEPTED,
            user=user,
            target=user,
            metadata={
                "email": user.email,
                "role": invitation.role,
                "player_id": invitation.player_id,
                "invited_by": invitation.invited_by.email if invitation.invited_by_id else None,
            },
        )
        # AND nothing else: no user_signed_up, no send_registration_received,
        # no notify_new_approval_request (plan: acceptance non-triggers).
        notification_service.send_invitation_completed(user, request=request)
        notify_invitation_completed(user)
        messages.success(request, _("Registration completed — you can now log in."))
        return redirect("account_login")


class SettingsView(LoginRequiredMixin, View):
    """Display, start page and e-mail preferences (password change: allauth)."""

    def _props(self, request, form):
        from app.players.avatars import avatars_for

        user = request.user
        player = user.player_link
        fields = form.fields

        def choice(name):
            return [{"value": str(v), "label": str(lbl)} for v, lbl in fields[name].choices]

        values = {}
        for name in fields:
            value = form[name].value()
            if hasattr(value, "strftime"):
                value = value.strftime("%H:%M")
            values[name] = value
        return {
            "values": values,
            "fields": list(fields),
            "choices": {
                "preferred_language": choice("preferred_language"),
                "preferred_theme": choice("preferred_theme"),
                "start_page": choice("start_page"),
                **(
                    {"penalty_notify_mode": choice("penalty_notify_mode")}
                    if "penalty_notify_mode" in fields
                    else {}
                ),
            },
            "player": (
                {
                    "id": player.pk,
                    "name": player.name,
                    "avatar": avatars_for([player.pk]).get(player.pk, ""),
                }
                if player
                else None
            ),
            # The club account is managed by a portal admin (no self-service).
            "managed": bool(user.is_club_account),
            "passwordUrl": "" if user.is_club_account else reverse("account_change_password"),
            "email": user.email,
            "pendingEmail": pending_email(user),
            "emailUrl": "" if user.is_club_account else reverse("accounts:settings_email"),
            "rightsUrl": reverse("rights"),
            "errors": form_errors(form) if form.is_bound else {},
            "emailErrors": {},
        }

    def get(self, request):
        return inertia_render(
            request,
            "Account/Settings",
            props=self._props(request, SettingsForm(instance=request.user)),
        )

    def post(self, request):
        form = SettingsForm(request_data(request), instance=request.user)
        if form.is_valid():
            from app.core.services import form_changes

            changes = form_changes(form)
            form.save()
            if {"penalty_notify_mode", "penalty_notify_time"} & set(form.changed_data):
                reschedule_pending(request.user)
            log_action(
                AuditAction.USER_UPDATED,
                user=request.user,
                target=request.user,
                metadata={"settings": changes},
            )
            messages.success(request, _("Settings saved."))
            response = redirect("accounts:settings")
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                form.cleaned_data["preferred_language"],
                max_age=settings.LANGUAGE_COOKIE_AGE,
                samesite="Lax",
            )
            translation.activate(form.cleaned_data["preferred_language"])
            return response
        return inertia_render(request, "Account/Settings", props=self._props(request, form))


def pending_email(user) -> str:
    """The address the user is changing to and has not confirmed yet ("" if none)."""
    from allauth.account.models import EmailAddress

    pending = (
        EmailAddress.objects.filter(user=user, verified=False)
        .exclude(email__iexact=user.email)
        .order_by("pk")
        .last()
    )
    return pending.email if pending else ""


class EmailChangeView(LoginRequiredMixin, View):
    """Change the own login address from the settings page.

    With e-mail verification on, the new address gets a confirmation link and
    replaces the old one only once it is confirmed (``ACCOUNT_CHANGE_EMAIL``);
    until then every mail and the login keep using the old address.
    """

    def post(self, request):
        from allauth.account.internal.flows.email_verification import (
            send_verification_email_to_address,
        )
        from allauth.account.models import EmailAddress

        user = request.user
        if user.is_club_account:
            messages.error(request, _("A portal admin manages the e-mail of the club account."))
            return redirect("accounts:settings")
        data = request_data(request)
        if data.get("action") == "cancel":
            EmailAddress.objects.filter(user=user, verified=False).exclude(
                email__iexact=user.email
            ).delete()
            messages.info(request, _("The e-mail change was withdrawn."))
            return redirect("accounts:settings")

        form = EmailChangeForm(user, data)
        if not form.is_valid():
            props = SettingsView()._props(request, SettingsForm(instance=user))
            props["emailErrors"] = form_errors(form)
            return inertia_render(request, "Account/Settings", props=props)

        new, old = form.cleaned_data["email"], user.email
        with transaction.atomic():
            # Only one change at a time: an older, unconfirmed request is dropped.
            EmailAddress.objects.filter(user=user, verified=False).exclude(
                email__iexact=old
            ).delete()
            if settings.ACCOUNT_EMAIL_VERIFICATION == "none":
                EmailAddress.objects.filter(user=user).delete()
                EmailAddress.objects.create(user=user, email=new, verified=True, primary=True)
                user.email = new
                user.save(update_fields=["email"])
            else:
                address = EmailAddress.objects.create(
                    user=user, email=new, verified=False, primary=False
                )
        log_action(
            AuditAction.USER_UPDATED,
            user=user,
            target=user,
            metadata={"email_change": {"from": old, "to": new}},
        )
        if settings.ACCOUNT_EMAIL_VERIFICATION == "none":
            messages.success(request, _("Your e-mail address was changed."))
        else:
            send_verification_email_to_address(request, address)
            messages.info(
                request,
                _(
                    "We sent a confirmation link to %(email)s. Until you confirm it, "
                    "your current address stays in use."
                )
                % {"email": new},
            )
        return redirect("accounts:settings")


class ThemeUpdateView(LoginRequiredMixin, View):
    """POST-only JSON endpoint used by the theme toggle of the app shell (``X-CSRFToken``)."""

    def post(self, request):
        theme = request.POST.get("theme", "")
        if theme not in ThemeChoice.values:
            return JsonResponse({"ok": False, "error": "invalid theme"}, status=400)
        request.user.preferred_theme = theme
        request.user.save(update_fields=["preferred_theme"])
        return JsonResponse({"ok": True, "theme": theme})
