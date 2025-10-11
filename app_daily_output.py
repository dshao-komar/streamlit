import streamlit as st
import pandas as pd
import base64
from datetime import date
from io import StringIO
import requests

# ---------------------------------------------------------
# Streamlit Page Config
# ---------------------------------------------------------
st.set_page_config(page_title="Daily Production Entry", layout="wide")
st.title("🧾 Daily Production Output Log")
st.caption("Submit daily machine output. Data is automatically saved to GitHub.")

# ---------------------------------------------------------
# GitHub Setup
# ---------------------------------------------------------
GITHUB_TOKEN = st.secrets["github_token"]
REPO = st.secrets["github_repo"]
FILE_PATH = st.secrets["github_file_path"]
BRANCH = st.secrets.get("github_branch", "main")
USER_EMAIL = st.secrets.get("github_user_email", "unknown@example.com")
USER_NAME = st.secrets.get("github_user_name", "Streamlit Bot")

API_URL = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# ---------------------------------------------------------
# Machine List
# ---------------------------------------------------------
MACHINES = [
    "Jenny", "Cutter 1", "Cutter 2", "Cutter 3", "Die Cutter",
    "PC1", "PC2", "PC3", "PC5", "AW1",
    "Sheeter 1", "Sheeter 2"
]

# ---------------------------------------------------------
# UI: Entry Form
# ---------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    entry_date = st.date_input("Production Date", value=date.today())
with col2:
    shift = st.selectbox("Shift", options=["Shift 1", "Shift 2"])

day_of_week = entry_date.strftime("%A")

st.markdown("---")
st.subheader("Enter Production Details per Machine")

# Build form layout
with st.form("daily_output_form", clear_on_submit=True):
    # Table-like header row
    header_cols = st.columns([2, 1.5, 1, 2])
    header_cols[0].markdown("**Machine**")
    header_cols[1].markdown("**LB Produced**")
    header_cols[2].markdown("**No Schedule**")
    header_cols[3].markdown("**Notes**")

    # Storage for user inputs
    rows = []
    for machine in MACHINES:
        c1, c2, c3, c4 = st.columns([2, 1.5, 1, 2])
        with c1:
            st.write(machine)
        with c2:
            lbs = st.number_input(
                f"{machine}_lbs",
                label_visibility="collapsed",
                min_value=0.0,
                step=1.0,
                value=0.0,
                key=f"lbs_{machine}"
            )
        with c3:
            no_schedule = st.checkbox(
                " ",
                key=f"no_sched_{machine}",
                label_visibility="collapsed"
            )
        with c4:
            notes = st.text_input(
                f"{machine}_notes",
                label_visibility="collapsed",
                placeholder="e.g. Sick Operator"
            )

        rows.append({
            "Machine Name": machine,
            "Total Produced (LB)": lbs,
            "No Schedule": "X" if no_schedule else "",
            "Notes": notes.strip()
        })

    submitted = st.form_submit_button("Submit Daily Output")

# ---------------------------------------------------------
# HELPER: Fetch + Commit File to GitHub
# ---------------------------------------------------------
def fetch_github_file():
    """Fetch existing CSV content and SHA for the GitHub file."""
    response = requests.get(API_URL, headers=HEADERS)
    if response.status_code == 200:
        content = base64.b64decode(response.json()["content"]).decode("utf-8")
        sha = response.json()["sha"]
        return content, sha
    elif response.status_code == 404:
        return "", None  # new file case
    else:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")

def commit_to_github(updated_csv, sha=None):
    """Commit updated CSV back to GitHub."""
    message = f"Add daily output log for {entry_date} ({shift})"
    content_encoded = base64.b64encode(updated_csv.encode()).decode()
    payload = {
        "message": message,
        "content": content_encoded,
        "branch": BRANCH,
        "committer": {"name": USER_NAME, "email": USER_EMAIL},
    }
    if sha:
        payload["sha"] = sha
    response = requests.put(API_URL, headers=HEADERS, json=payload)
    if response.status_code not in [200, 201]:
        raise Exception(f"GitHub commit failed: {response.status_code} - {response.text}")
    return response.json()

# ---------------------------------------------------------
# PROCESS SUBMISSION
# ---------------------------------------------------------
if submitted:
    # Basic validation
    if (lbs == 0) and (not no_schedule):
        st.error("If machine had 0 production, please check the box for No Schedule.")
    else:
        df_new = pd.DataFrame(rows)
        df_new.insert(0, "Machine Name", df_new.pop("Machine Name"))
        df_new.insert(1, "Date", entry_date)
        df_new.insert(2, "Day of Week", day_of_week)
        df_new.insert(3, "Shift", shift)

        try:
            content, sha = fetch_github_file()
            if content.strip():
                df_existing = pd.read_csv(StringIO(content))
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new

            csv_buffer = StringIO()
            df_combined.to_csv(csv_buffer, index=False)
            commit_to_github(csv_buffer.getvalue(), sha)

            st.success(f"✅ Data submitted and saved to GitHub for {entry_date} ({shift})!")
            st.dataframe(df_new)

        except Exception as e:
            st.error(f"❌ Error updating GitHub file: {e}")
