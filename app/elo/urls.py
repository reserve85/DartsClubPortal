from django.urls import path

from app.elo import views

app_name = "elo"

urlpatterns = [
    path("", views.RankingView.as_view(), name="ranking"),
    path("all-time/", views.AllTimeView.as_view(), name="all_time"),
    path("matches/", views.MatchListView.as_view(), name="match_list"),
    path("matches/new/", views.MatchCreateView.as_view(), name="match_create"),
    path("matches/<int:pk>/", views.MatchDetailView.as_view(), name="match_detail"),
    path("matches/<int:pk>/edit/", views.MatchUpdateView.as_view(), name="match_update"),
    path("matches/<int:pk>/delete/", views.MatchDeleteView.as_view(), name="match_delete"),
    path("players/<int:pk>/", views.PlayerDetailView.as_view(), name="player_detail"),
    path("head-to-head/", views.HeadToHeadView.as_view(), name="h2h"),
    path("manage/", views.ManageView.as_view(), name="manage"),
    path("manage/recalculate/", views.RecalculateView.as_view(), name="recalculate"),
    path("manage/players/add/", views.PlayerAddView.as_view(), name="player_add"),
    path("manage/players/<int:pk>/edit/", views.PlayerEditView.as_view(), name="player_edit"),
    path("manage/players/<int:pk>/toggle/", views.PlayerToggleView.as_view(), name="player_toggle"),
    path("export/matches.csv", views.ExportMatchesCsvView.as_view(), name="export_matches"),
    path("export/players.csv", views.ExportPlayersCsvView.as_view(), name="export_players"),
    path("export/ranking.csv", views.ExportRankingCsvView.as_view(), name="export_ranking"),
]
