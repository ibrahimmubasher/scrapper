# Scraper Project Team Guide

This repository contains a Django-based scraper application for collecting and exporting business activity data from multiple jurisdictions. The project is configured for local development and is intended to be run on a developer machine rather than a cloud deployment.

## 1. Project purpose

The application provides:
- a local web dashboard for launching scrapers
- background scraper execution with progress and log tracking
- CSV and Excel export generation
- integration with activity matching and reconciliation services

## 2. Repository structure

- [manage.py](manage.py) — Django entry point
- [my_scraper](my_scraper) — Django project settings and routing
- [scraper](scraper) — main app with views, URLs, management commands, services, templates, and output folders
- [requirements.txt](requirements.txt) — Python dependencies
- [scraper/data](scraper/data) — local data assets and cached resources
- [scraper/output](scraper/output) — generated CSV/log/progress files

## 3. Prerequisites

Make sure these are installed before you start:
- Python 3.10+ (recommended 3.11 or 3.12)
- Git
- A local browser runtime for Playwright/Selenium-based scrapers
- Internet access for the target websites

## 4. Local setup on Windows

### 4.1 Create and activate a virtual environment

```powershell
cd C:\Users\OTS\Desktop\my_scraper
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

### 4.2 Install dependencies

```powershell
pip install -r requirements.txt
```

### 4.3 Verify Django setup

```powershell
python manage.py check
```

If the check passes, the project is configured correctly.

## 5. Environment variables

The project reads settings from environment variables and the local [.env](.env) file when present.

Useful variables include:
- SECRET_KEY
- DEBUG
- ALLOWED_HOSTS
- CSRF_TRUSTED_ORIGINS

Example:

```env
SECRET_KEY=local-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

## 6. Running the project locally

### 6.1 Start the Django web app

```powershell
python manage.py runserver
```

Then open:
- http://127.0.0.1:8000/

### 6.2 Run scrapers from the UI

Open the dashboard in the browser and use the available website selector to start a run.

### 6.3 Run scrapers from the command line

```powershell
python manage.py run_scrapers --website ALL
```

Optional:

```powershell
python manage.py run_scrapers --website SPC --progress-file scraper/output/my_run_progress.json
```

## 7. How the app works

### 7.1 Main workflow

1. The dashboard starts a scraper run.
2. The Django management command prepares the run and updates progress information.
3. The scraper services collect data from the selected websites.
4. Output files such as CSVs, logs, and progress JSON are written to [scraper/output](scraper/output).
5. The dashboard shows the generated outputs and allows the user to inspect logs.

### 7.2 Important folders

- [scraper/data](scraper/data) — supporting data, model assets, and cached values
- [scraper/output](scraper/output) — generated run artifacts
- [scraper/services](scraper/services) — scraper implementations and matching logic
- [scraper/templates/scraper](scraper/templates/scraper) — dashboard UI templates

## 8. Common team use cases

### Case 1: Fresh developer setup

Use this when a teammate is setting up the project on a new machine.

Steps:
1. Clone the repository.
2. Create and activate the virtual environment.
3. Install dependencies.
4. Run Django system checks.
5. Start the app with runserver.

### Case 2: Running scrapers manually

Use this when you want to run scraper jobs outside the browser UI.

Command:

```powershell
python manage.py run_scrapers --website ALL
```

### Case 3: Checking progress and logs

Use this when a scraper job is running or failed.

- Progress files are created in [scraper/output](scraper/output)
- Logs are written with the same run identifier
- The dashboard exposes the log and progress links for active runs

### Case 4: Re-running after a previous run

Previous output files are cleaned before a new run starts, so the latest results are easier to inspect.

### Case 5: Debugging a scrape failure

If a scraper run fails:
1. Open the generated log file in [scraper/output](scraper/output)
2. Review the traceback and error message
3. Re-run the affected website specifically if needed
4. Confirm that the required browser/runtime dependencies are present

### Case 6: Working with generated exports

Generated CSVs and logs are stored in [scraper/output](scraper/output). The dashboard can be used to inspect available output files.

## 9. Troubleshooting

### Browser dependency issues

If Playwright or Selenium-based scrapers fail, make sure the browser runtime is installed and available. Reinstalling dependencies and verifying the environment often resolves this.

### Import or module errors

If Django reports missing modules:

```powershell
pip install -r requirements.txt
```

### Missing output files

If the dashboard does not show expected outputs:
- check that the run completed successfully
- verify that [scraper/output](scraper/output) exists
- inspect the run log for warnings or exceptions

### Environment variable issues

If settings do not load as expected:
- confirm the [.env](.env) file exists and contains the needed values
- restart the Django server after editing environment values

## 10. Recommended team workflow

- Keep code changes small and focused.
- Run Django checks before sharing changes.
- Keep output folders and local temp output clean.
- Share logs and error messages when debugging scraper issues.
- Avoid committing large generated artifacts unless the team explicitly wants them in the repository.

## 11. Useful verification commands

```powershell
python manage.py check
python manage.py runserver
python manage.py run_scrapers --website ALL
```

## 12. Summary

For the team, the main local workflow is:
1. activate the virtual environment
2. install requirements
3. start Django with runserver
4. launch scrapers from the dashboard or command line
5. inspect outputs and logs in [scraper/output](scraper/output)
