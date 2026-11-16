"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

from app.accounts.qr import LegacyAutoLoginView, QrLoginView
from app.core import views as core_views
from app.core.modules import ELO, PENALTY, enabled_modules
from app.players.avatars import AvatarFileView, AvatarUploadView

_MODULES = enabled_modules()

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("health/", core_views.HealthView.as_view(), name="health"),
    # Old printed QR codes of the Elo system (paths unchanged on purpose).
    path("ui/qr-login", QrLoginView.as_view(legacy=True), name="legacy_qr_login"),
    path("auth/auto-login", LegacyAutoLoginView.as_view(), name="legacy_auto_login"),
]

PENALTY_URLS = [
    path("", include("app.dashboard.urls")),
    path("teams/", include("app.teams.urls")),
    path("players/", include("app.players.urls")),
    path("matchdays/", include("app.matchdays.urls")),
    path("", include("app.penalties.urls")),
    path("seasons/", core_views.SeasonListView.as_view(), name="season_list"),
    path("seasons/create/", core_views.SeasonCreateView.as_view(), name="season_create"),
    path("seasons/<int:pk>/update/", core_views.SeasonUpdateView.as_view(), name="season_update"),
    path(
        "seasons/<int:pk>/set-default/",
        core_views.SeasonSetDefaultView.as_view(),
        name="season_set_default",
    ),
    path("seasons/<int:pk>/delete/", core_views.SeasonDeleteView.as_view(), name="season_delete"),
    path("seasons/set/", core_views.SeasonSetView.as_view(), name="season_set"),
]

urlpatterns += i18n_patterns(
    # django-allauth first: login/logout/signup/password/e-mail verification.
    # Path overlaps with app.accounts are avoided by design (settings/, users/).
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("app.accounts.urls")),
    # django-notifications-hq: list/unread/mark-as-read of in-app notifications
    path("notifications/", include("notifications.urls")),
    # Custom mailbox actions (delete one / delete read) — mounted AFTER the
    # package include so the package keeps owning every notifications:* name.
    path("notifications/actions/", include("app.notifications.urls")),
    # "/" forwards to the user's start page (Elo, penalty or overview - see
    # app/core/access.py); modules are routed only when enabled.
    path("", core_views.HomeView.as_view(), name="home"),
    path("overview/", core_views.OverviewView.as_view(), name="overview"),
    *(PENALTY_URLS if PENALTY in _MODULES else []),
    *([path("elo/", include("app.elo.urls"))] if ELO in _MODULES else []),
    path("audit/", core_views.AuditLogListView.as_view(), name="audit_list"),
    path("import/", include("app.importer.urls")),
    path("avatars/upload/", AvatarUploadView.as_view(), name="avatar_upload"),
    path("avatars/<str:name>", AvatarFileView.as_view(), name="player_avatar"),
    path("imprint/", core_views.ImprintView.as_view(), name="imprint"),
    path("privacy/", core_views.PrivacyView.as_view(), name="privacy"),
    prefix_default_language=False,
)
