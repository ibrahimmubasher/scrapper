web: bash -lc "python -m playwright install chromium && python manage.py migrate && python manage.py collectstatic --noinput && gunicorn my_scraper.wsgi --bind 0.0.0.0:$PORT"
