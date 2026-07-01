import json
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
import os

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from scraper.paths_config import OUTPUT_DIR as _OUTPUT_DIR_STR

from scraper.management.commands.run_scrapers import update_progress_status


BASE_DIR = Path(__file__).resolve().parent.parent
MANAGE_PY = BASE_DIR / "manage.py"
OUTPUT_DIR = Path(_OUTPUT_DIR_STR)
WEBSITES = ["ALL", "RAKEZ", "MEYDAN", "ANCF", "IFZA", "SHAMS", "SPC", "AFZ", "SRTIP"]


def view_log(request, run_id):
    """Display the log for a completed or in-progress scraper run."""
    log_path = OUTPUT_DIR / f"{run_id}.log"
 
    if not log_path.exists():
        return HttpResponse(
            f"No log file found for run_id: {run_id}",
            content_type="text/plain",
            status=404,
        )
 
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return HttpResponse(
            f"Unable to read log file: {exc}",
            content_type="text/plain",
            status=500,
        )
 
    return HttpResponse(content, content_type="text/plain")
 
def _list_output_files():
    if not OUTPUT_DIR.exists():
        return []
    return sorted([path.name for path in OUTPUT_DIR.glob("*.csv")])

def clear_previous_outputs():
    """
    Remove all previous generated files before starting a new run.
    """

    if not OUTPUT_DIR.exists():
        return

    patterns = [
        "*.csv",
        "*.log",
        "*_progress.json",
    ]

    for pattern in patterns:

        for file in OUTPUT_DIR.glob(pattern):

            try:
                file.unlink()

            except Exception as e:
                print(f"Could not delete {file}: {e}")
def dashboard(request):
    selected_website = (request.POST.get("website") or "ALL").upper()
    run_result = None
    output_files = _list_output_files()

    if request.method == "POST" and request.POST.get("run") == "1":
        try:
            completed = subprocess.run(
                [sys.executable, str(MANAGE_PY), "run_scrapers", "--website", selected_website],
                capture_output=True,
                text=True,
                cwd=str(BASE_DIR),
                timeout=1800,
            )

            run_result = {
                "success": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
            }
            output_files = _list_output_files()

        except subprocess.TimeoutExpired:
            run_result = {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "The scraper took too long to finish.",
            }
        except Exception as exc:
            run_result = {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(exc),
            }

    context = {
        "websites": WEBSITES,
        "selected_website": selected_website,
        "output_files": output_files,
        "run_result": run_result,
    }
    return render(request, "scraper/dashboard.html", context)


def start_run(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST requests are allowed."}, status=405)
 
    selected_website = (request.POST.get("website") or "ALL").upper()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Remove previous outputs
    clear_previous_outputs()
 
    run_id = uuid.uuid4().hex[:10]
    progress_file = OUTPUT_DIR / f"{run_id}_progress.json"
    log_file = OUTPUT_DIR / f"{run_id}.log"
 
    update_progress_status(progress_file, "queued", "Queued", 0, selected_website)
 
    command = [
        sys.executable,
        "-u",                          # ← unbuffered stdout, logs show immediately
        str(MANAGE_PY),
        "run_scrapers",
        "--website",
        selected_website,
        "--progress-file",
        str(progress_file),
    ]
 
    log_handle = log_file.open("w", encoding="utf-8")
 
    env = os.environ.copy()
 
    try:
        subprocess.Popen(
            command,
            cwd=str(BASE_DIR),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except Exception as exc:
        log_handle.close()
        return JsonResponse(
            {
                "success": False,
                "error": f"Failed to launch scraper process: {exc}",
            },
            status=500,
        )
    finally:
        log_handle.close()
 
    return JsonResponse(
        {
            "success": True,
            "run_id": run_id,
            "status_url": reverse("progress_status", args=[run_id]),
            "log_url": reverse("view_log", args=[run_id]),
            "output_files": _list_output_files(),
        }
    )
def _tail_log(log_path, max_lines=40, max_bytes=8192):
    try:
        with log_path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            offset = min(file_size, max_bytes)
            f.seek(file_size - offset)
            data = f.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

    lines = data.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def progress_status(request, run_id):
    progress_file = OUTPUT_DIR / f"{run_id}_progress.json"
    log_path = OUTPUT_DIR / f"{run_id}.log"

    if not progress_file.exists():
        payload = {"status": "queued", "message": "Preparing run", "percent": 0}
    else:
        try:
            payload = json.loads(progress_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"status": "running", "message": "Working on your request", "percent": 0}
        except Exception as exc:
            return JsonResponse(
                {"status": "failed", "message": f"Unable to read progress file: {exc}", "percent": 0},
                status=500,
            )

    payload["output_files"] = _list_output_files()
    payload["run_id"] = run_id
    payload["log_url"] = reverse("view_log", args=[run_id])
    payload["log_tail"] = _tail_log(log_path)
    response = JsonResponse(payload)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


def download_csv(request, website):
    csv_path = OUTPUT_DIR / f"{website}.csv"

    if not csv_path.exists():
        raise Http404("CSV file not found")

    return FileResponse(open(csv_path, "rb"), as_attachment=True, filename=f"{website}.csv")


def _build_scraper_zip(dataframes):
    import io
    import zipfile

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name, dataframe in dataframes.items():
            excel_buffer = io.BytesIO()
            dataframe.to_excel(excel_buffer, index=False, engine="openpyxl")
            zip_file.writestr(f"{name}.xlsx", excel_buffer.getvalue())

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def scrape_api(request):
    try:
        print("\nRunning selected scrapers...")
        from .services.maydan_service import scrape_meydan
        from .services.SPC_scraper import scrape_SPC_activities
        from .services.Ajman_scraper import scrape_AFZ_activities

        dataframes = {
            "meydan": scrape_meydan(),
            "SPC": scrape_SPC_activities(),
            "AFZ": scrape_AFZ_activities(),
        }

        archive = _build_scraper_zip(dataframes)
        response = HttpResponse(archive, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="all_scrapers.zip"'
        return response

    except Exception as exc:
        print(traceback.format_exc())
        return HttpResponse(f"ERROR: {str(exc)}", status=500)