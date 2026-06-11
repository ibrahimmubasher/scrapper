from django.urls import path
from .views import scrape_api

urlpatterns = [
    path('scrape/', scrape_api, name='scrape_api'),
]