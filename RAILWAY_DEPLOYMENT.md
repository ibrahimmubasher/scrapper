# Web Scraper Dashboard

A Django-based web scraper dashboard for collecting and managing activities from multiple UAE jurisdictions.

## Deployment to Railway

### Prerequisites
- A Railway account (railway.app)
- Git installed and repo initialized
- Project pushed to GitHub/GitLab

### Deployment Steps

1. **Connect Your Repository**
   - Log in to [Railway](https://railway.app)
   - Create a new project
   - Connect your GitHub repository

2. **Set Environment Variables in Railway**
   In the Railway project settings, add these variables:
   ```
   DEBUG=False
   SECRET_KEY=your-secret-key-here
   ALLOWED_HOSTS=your-domain.up.railway.app,www.your-domain.up.railway.app
   ```

3. **Deploy**
   - Railway will automatically detect the Procfile and runtime.txt
   - The app will be built and deployed automatically
   - Your domain will be provided (e.g., `project-name.up.railway.app`)

### How It Works

- **Procfile**: Runs Django migrations and starts Gunicorn WSGI server
- **runtime.txt**: Specifies Python 3.13.0
- **requirements.txt**: Contains all necessary dependencies

### Local Testing

Before deploying, test locally:

```bash
# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start dev server
python manage.py runserver
```

### Features

- Select and run web scrapers for different UAE jurisdictions
- Real-time progress tracking with progress bar
- Automatic CSV export of scraper results
- Activity matching and deduplication
- ISIC classification of activities

### Supported Websites

- RAKEZ
- MEYDAN
- ANCF
- IFZA
- SHAMS
- SPC
- AFZ
- SRTIP

---

**Note**: Ensure all sensitive information is stored in Railway environment variables, not in code.
