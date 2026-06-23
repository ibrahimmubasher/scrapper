web: bash -lc "python3 -m playwright install chromium && python3 manage.py migrate && python3 manage.py collectstatic --noinput && gunicorn my_scraper.wsgi --bind 0.0.0.0:$PORT"
