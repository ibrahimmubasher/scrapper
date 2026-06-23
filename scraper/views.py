import json
import subprocess
import sys
import traceback
import uuid
from pathlib import Path

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
            content_type="text/plain"
        )
 
    content = log_path.read_text(encoding="utf-8", errors="replace")
 
    return HttpResponse(content, content_type="text/plain")
 
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
        str(MANAGE_PY),
        "run_scrapers",
        "--website",
        selected_website,
        "--progress-file",
        str(progress_file),
    ]

    log_handle = log_file.open("w", encoding="utf-8")
    subprocess.Popen(command, cwd=str(BASE_DIR), stdout=log_handle, stderr=subprocess.STDOUT)

    return JsonResponse(
        {
            "success": True,
            "run_id": run_id,
            "status_url": reverse("progress_status", args=[run_id]),
            "output_files": _list_output_files(),
        }
    )


def progress_status(request, run_id):
    progress_file = OUTPUT_DIR / f"{run_id}_progress.json"

    if not progress_file.exists():
        return JsonResponse({"status": "queued", "message": "Preparing run", "percent": 0})

    try:
        payload = json.loads(progress_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {"status": "running", "message": "Working on your request", "percent": 0}

    payload["output_files"] = _list_output_files()
    payload["run_id"] = run_id
    return JsonResponse(payload)


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