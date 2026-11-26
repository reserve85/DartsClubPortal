from django.urls import path

from app.matchdays import views
from app.matchdays.calendar import MatchdayCalendarView

app_name = "matchdays"

urlpatterns = [
    path("", views.MatchdayListView.as_view(), name="matchday_list"),
    path("create/", views.MatchdayCreateView.as_view(), name="matchday_create"),
    path("nuliga/sync/", views.NuligaSyncView.as_view(), name="nuliga_sync"),
    path("calendar/<str:token>.ics", MatchdayCalendarView.as_view(), name="calendar"),
    path("<int:pk>/", views.MatchdayDetailView.as_view(), name="matchday_detail"),
    path(
        "<int:pk>/participants/",
        views.MatchdayParticipantsView.as_view(),
        name="matchday_participants",
    ),
    path("<int:pk>/edit/", views.MatchdayUpdateView.as_view(), name="matchday_update"),
    path("<int:pk>/delete/", views.MatchdayDeleteView.as_view(), name="matchday_delete"),
]
