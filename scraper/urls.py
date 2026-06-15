from django.urls import path
from .views import dashboard, download_csv, progress_status, scrape_api, start_run

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('scrape/', scrape_api, name='scrape_api'),
    path('run/', start_run, name='start_run'),
    path('progress/<str:run_id>/', progress_status, name='progress_status'),
    path('download/<str:website>/', download_csv, name='download_csv'),
]