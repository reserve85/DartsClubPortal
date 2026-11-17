"""Account URL routes.

Login/logout/signup/password reset & change/email verification are served by
django-allauth (mounted in ``config/urls.py`` before this module). Only the
application-specific pages live here.
"""

from django.urls import path

from app.accounts import qr, views

app_name = "accounts"

urlpatterns = [
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("qr/", qr.QrLoginView.as_view(), name="qr_login"),
    path("users/<int:pk>/qr/", qr.UserQrCodeView.as_view(), name="user_qr"),
    path("settings/theme/", views.ThemeUpdateView.as_view(), name="settings_theme"),
    path("settings/email/", views.EmailChangeView.as_view(), name="settings_email"),
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/create/", views.UserCreateView.as_view(), name="user_create"),
    path("users/invitations/", views.InviteListView.as_view(), name="invite_list"),
    path("users/invitations/create/", views.InviteCreateView.as_view(), name="invite_create"),
    path(
        "users/invitations/<int:pk>/resend/",
        views.InviteResendView.as_view(),
        name="invite_resend",
    ),
    path(
        "users/invitations/<int:pk>/cancel/",
        views.InviteCancelView.as_view(),
        name="invite_cancel",
    ),
    # Public acceptance page (allauth entrance area: no login required).
    path("invite/<str:token>/", views.InviteAcceptView.as_view(), name="invite_accept"),
    path("users/pending/", views.PendingUserListView.as_view(), name="approval_list"),
    path("users/<int:pk>/approval/", views.UserApprovalView.as_view(), name="approval"),
    path("users/<int:pk>/update/", views.UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/deactivate/", views.UserDeactivateView.as_view(), name="user_deactivate"),
    path(
        "users/<int:pk>/password/",
        views.UserSetPasswordView.as_view(),
        name="user_set_password",
    ),
]
