from django.urls import path

from app.players import members, views

app_name = "players"

urlpatterns = [
    # Members: every person with teams, Elo and account in one place.
    path("", members.MemberListView.as_view(), name="player_list"),
    path("create/", members.MemberCreateView.as_view(), name="player_create"),
    path("quick-add/", members.MemberQuickAddView.as_view(), name="member_quick_add"),
    path("<int:pk>/", views.PlayerDetailView.as_view(), name="player_detail"),
    path("<int:pk>/edit/", members.MemberEditView.as_view(), name="player_update"),
    path("<int:pk>/deactivate/", views.PlayerDeactivateView.as_view(), name="player_deactivate"),
]
