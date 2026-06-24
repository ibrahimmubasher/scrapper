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

from scraper.management.commands.run_scrapers import update_progress_status

BASE_DIR = Path(__file__).resolve().parent.parent
MANAGE_PY = BASE_DIR / "manage.py"
OUTPUT_DIR = BASE_DIR / "scraper" / "output"
WEBSITES = ["ALL", "RAKEZ", "MEYDAN", "ANCF", "IFZA", "SHAMS", "SPC", "AFZ", "SRTIP"]


def view_log(request, run_id):
    """
    Debug helper: lets you view the subprocess log file
    in the browser instead of needing SSH/console access.
 
    Visit: https://your-app.up.railway.app/log/<run_id>/
    """
    log_path = OUTPUT_DIR / f"{run_id}.log"
 
    if not log_path.exists():
        return HttpResponse(
            f"No log file found for run_id: {run_id}",
            content_type="text/plain; charset=utf-8"
        )
 
    raw_content = log_path.read_text(encoding="utf-8", errors="replace")
 
    # Strip ANSI escape codes (color codes from terminal output)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', raw_content)
 
    # Strip other control characters except newline/tab
    cleaned = ''.join(
        ch for ch in cleaned
        if ch in ('\n', '\t', '\r') or (ord(ch) >= 32 and ord(ch) != 127)
    )
 
    # Escape HTML special characters so progress bars / symbols
    # don't get interpreted as HTML
    cleaned = (
        cleaned
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
 
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Log: {run_id}</title></head>
<body style="background:#0b0b0f; color:#ddd; font-family:monospace;">
<pre style="white-space:pre-wrap; word-wrap:break-word; padding:20px;">{cleaned}</pre>
</body>
</html>"""
 
    return HttpResponse(html, content_type="text/html; charset=utf-8")
 
def _list_output_files():
    if not OUTPUT_DIR.exists():
        return []
    return sorted([path.name for path in OUTPUT_DIR.glob("*.csv")])


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
 
    # ── KEY FIX ──────────────────────────────────────────
    # Explicitly pass full environment to the child process
    # so OPENAI_API_KEY and all Railway variables are visible
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


def scrape_api(request):
    try:
        print("\nRunning Meydan scraper...")
        from .services.maydan_service import scrape_meydan
        from .services.SPC_scraper import scrape_SPC_activities
        from .services.Ajman_scraper import scrape_AFZ_activities

        df_meydan = scrape_meydan()
        df_SPC = scrape_SPC_activities()
        df_AFZ = scrape_AFZ_activities()

        import io
        import zipfile

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            meydan_buffer = io.BytesIO()
            df_meydan.to_excel(meydan_buffer, index=False, engine="openpyxl")
            zip_file.writestr("meydan.xlsx", meydan_buffer.getvalue())

            SPC_buffer = io.BytesIO()
            df_SPC.to_excel(SPC_buffer, index=False, engine="openpyxl")
            zip_file.writestr("SPC.xlsx", SPC_buffer.getvalue())

            AFZ_buffer = io.BytesIO()
            df_AFZ.to_excel(AFZ_buffer, index=False, engine="openpyxl")
            zip_file.writestr("AFZ.xlsx", AFZ_buffer.getvalue())

        zip_buffer.seek(0)

        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="all_scrapers.zip"'
        return response

    except Exception as exc:
        print(traceback.format_exc())
        return HttpResponse(f"ERROR: {str(exc)}", status=500)
    try:
        print("\nRunning Meydan scraper...")
        from .services.maydan_service import scrape_meydan
        from .services.SPC_scraper import scrape_SPC_activities
        from .services.Ajman_scraper import scrape_AFZ_activities

        df_meydan = scrape_meydan()
        df_SPC = scrape_SPC_activities()
        df_AFZ = scrape_AFZ_activities()

        import io
        import zipfile

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            meydan_buffer = io.BytesIO()
            df_meydan.to_excel(meydan_buffer, index=False, engine="openpyxl")
            zip_file.writestr("meydan.xlsx", meydan_buffer.getvalue())

            SPC_buffer = io.BytesIO()
            df_SPC.to_excel(SPC_buffer, index=False, engine="openpyxl")
            zip_file.writestr("SPC.xlsx", SPC_buffer.getvalue())

            AFZ_buffer = io.BytesIO()
            df_AFZ.to_excel(AFZ_buffer, index=False, engine="openpyxl")
            zip_file.writestr("AFZ.xlsx", AFZ_buffer.getvalue())

        zip_buffer.seek(0)

        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="all_scrapers.zip"'
        return response

    except Exception as exc:
        print(traceback.format_exc())
        return HttpResponse(f"ERROR: {str(exc)}", status=500)