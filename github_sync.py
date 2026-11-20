import os
import shutil
import subprocess

REPO_PATH = r"C:\Users\Streamlit.WISSIND\Wabtec_Qlik_DB-s"

SOURCE_FILE = (
    r"C:\Users\Streamlit.WISSIND\OneDrive - Wabtec Corporation"
    r"\DataDog_Alerting\qlik\Streamlit_qlik\New folder\Expected_sheet.xlsx"
)

TARGET_FILE = os.path.join(REPO_PATH, "Expected_sheet.xlsx")


def push_dashboard_update():

    shutil.copy2(SOURCE_FILE, TARGET_FILE)

    os.chdir(REPO_PATH)

    status = subprocess.run(
        ["git", "status", "--porcelain", "Expected_sheet.xlsx"],
        capture_output=True,
        text=True
    )

    if not status.stdout.strip():
        print("No changes detected.")
        return

    subprocess.run(
        ["git", "add", "Expected_sheet.xlsx"],
        check=True
    )

    subprocess.run(
        ["git", "commit", "-m", "Auto refresh dashboard data"],
        check=True
    )

    subprocess.run(
        ["git", "pull", "--rebase", "origin", "Uday"],
        check=True
    )

    subprocess.run(
        ["git", "push", "origin", "Uday"],
        check=True
    )

    print("GitHub updated successfully.")
