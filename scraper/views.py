import io
import zipfile
import traceback

from django.http import HttpResponse

from .services.maydan_service import scrape_meydan
from .services.SPC_scraper import scrape_SPC_activities
from .services.Ajman_scraper import scrape_AFZ_activities


def scrape_api(request):

    try:

        # ==========================================
        # RUN SCRAPERS
        # ==========================================

        print("\nRunning Meydan scraper...")
        df_meydan = scrape_meydan()

        print("\nRunning SPC scraper...")
        df_SPC = scrape_SPC_activities()

        print("\nRunning AFZ scraper...")
        df_AFZ = scrape_AFZ_activities()

        # ==========================================
        # CREATE ZIP IN MEMORY
        # ==========================================

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(
            zip_buffer,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zip_file:

            # ======================================
            # MEYDAN
            # ======================================

            meydan_buffer = io.BytesIO()

            df_meydan.to_excel(
                meydan_buffer,
                index=False,
                engine="openpyxl"
            )

            zip_file.writestr(
                "meydan.xlsx",
                meydan_buffer.getvalue()
            )

            # ======================================
            # SPC
            # ======================================

            SPC_buffer = io.BytesIO()

            df_SPC.to_excel(
                SPC_buffer,
                index=False,
                engine="openpyxl"
            )

            zip_file.writestr(
                "SPC.xlsx",
                SPC_buffer.getvalue()
            )

            # ======================================
            # AFZ
            # ======================================

            AFZ_buffer = io.BytesIO()

            df_AFZ.to_excel(
                AFZ_buffer,
                index=False,
                engine="openpyxl"
            )

            zip_file.writestr(
                "AFZ.xlsx",
                AFZ_buffer.getvalue()
            )

        zip_buffer.seek(0)

        # ==========================================
        # DOWNLOAD RESPONSE
        # ==========================================

        response = HttpResponse(
            zip_buffer.getvalue(),
            content_type="application/zip"
        )

        response[
            "Content-Disposition"
        ] = 'attachment; filename="all_scrapers.zip"'

        return response

    except Exception as e:

        print(traceback.format_exc())

        return HttpResponse(
            f"ERROR: {str(e)}",
            status=500
        )