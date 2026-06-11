import os
import subprocess
import streamlit as st

# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="Activity Scraper Dashboard",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Activity Scraper Dashboard")

st.markdown(
    """
Run a single website scraper or all scrapers.
After completion you can download the generated CSV.
"""
)

st.divider()

# =====================================================
# WEBSITES
# =====================================================

WEBSITES = [
    "ALL",
    "RAKEZ",
    "MEYDAN",
    "ANCF",
    "IFZA",
    "SHAMS",
    "SPC",
    "AFZ",
    "SRTIP"
]

# =====================================================
# UI
# =====================================================

col1, col2 = st.columns([3, 1])

with col1:

    selected_website = st.selectbox(
        "Select Website",
        WEBSITES
    )

with col2:

    st.write("")
    st.write("")

    run_button = st.button(
        "🚀 Run Scraper",
        use_container_width=True
    )

st.divider()

# =====================================================
# RUN
# =====================================================

if run_button:

    with st.spinner(f"Running {selected_website}..."):

        result = subprocess.run(

            [
                "python",
                "manage.py",
                "run_scrapers",
                "--website",
                selected_website
            ],

            capture_output=True,
            text=True
        )

    if result.returncode == 0:

        st.success("Scraper completed successfully.")

    else:

        st.error("Scraper finished with errors.")

    # =================================================
    # LOGS
    # =================================================

    st.subheader("Execution Logs")

    st.code(
        result.stdout,
        language="text"
    )

    if result.stderr:

        st.subheader("Errors")

        st.code(
            result.stderr,
            language="text"
        )

    # =================================================
    # DOWNLOAD CSV
    # =================================================

    if selected_website != "ALL":

        csv_path = os.path.join(

            "scraper",
            "output",
            f"{selected_website}.csv"

        )

        if os.path.exists(csv_path):

            st.divider()

            st.subheader("Download CSV")

            with open(csv_path, "rb") as file:

                st.download_button(

                    label=f"📥 Download {selected_website}.csv",

                    data=file,

                    file_name=f"{selected_website}.csv",

                    mime="text/csv",

                    use_container_width=True

                )

        else:

            st.warning("CSV file was not generated.")

    else:

        st.divider()

        st.info(
            "ALL mode completed. Individual CSV files are available inside scraper/output/."
        )