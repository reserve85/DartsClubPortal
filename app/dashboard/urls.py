from django.urls import path

from app.dashboard import views

app_name = "dashboard"

urlpatterns = [
    # The financial overview IS the start page — the old Dashboard/Übersicht
    # page only repeated the team list and was removed.
    # "/" is the portal start page now; "index" stays as an alias name.
    path("financial/", views.FinancialOverviewView.as_view(), name="index"),
    path("financial/", views.FinancialOverviewView.as_view(), name="financial_overview"),
]
