from django.urls import path

from app.importer import views

app_name = "importer"

urlpatterns = [
    path("", views.ImportView.as_view(), name="import"),
]
