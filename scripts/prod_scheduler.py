import streamlit as st
import pandas as pd
import pyodbc
import plotly.express as px
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load .env values
load_dotenv()

uid = os.getenv("STREAMLIT_DB_USER")
pwd = os.getenv("STREAMLIT_DB_PASS")
server = "172.22.4.20,1433"
database = "P21"

# ---------------------------------------------------------
# Streamlit Config
# ---------------------------------------------------------
st.set_page_config(page_title="Production Weight Dashboard", layout="wide")
st.title("⚙️ Total Production Weight by Machine & Scheduler")

# ---------------------------------------------------------
# SQL Connection
# ---------------------------------------------------------
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={server};DATABASE={database};UID={uid};PWD={pwd};"
)
conn = pyodbc.connect(conn_str)

# ---------------------------------------------------------
# Query
# ---------------------------------------------------------
query = """
    SELECT 
        p21_view_prod_order_hdr.prod_order_number,
        p21_view_prod_order_hdr.expected_completion_date,
        prod_order_hdr_ud.production_machine,
        p21_view_inv_mast.net_weight * p21_view_prod_order_line.qty_to_make AS extended_weight,
        users.name AS scheduler_name
    FROM 
        P21.dbo.p21_view_prod_order_hdr AS p21_view_prod_order_hdr
        INNER JOIN P21.dbo.p21_view_prod_order_line AS p21_view_prod_order_line
            ON p21_view_prod_order_hdr.prod_order_number = p21_view_prod_order_line.prod_order_number
        LEFT OUTER JOIN P21.dbo.prod_order_hdr_ud AS prod_order_hdr_ud
            ON p21_view_prod_order_hdr.prod_order_number = prod_order_hdr_ud.prod_order_number
        INNER JOIN P21.dbo.p21_view_inv_mast AS p21_view_inv_mast
            ON p21_view_prod_order_line.inv_mast_uid = p21_view_inv_mast.inv_mast_uid
        INNER JOIN P21.dbo.p21_view_inv_loc AS p21_view_inv_loc
            ON p21_view_inv_mast.inv_mast_uid = p21_view_inv_loc.inv_mast_uid
        INNER JOIN P21.dbo.users AS users
            ON users.id = p21_view_prod_order_hdr.entered_by
    WHERE 
        p21_view_inv_loc.location_id = 210
        AND p21_view_prod_order_hdr.cancel = 'N'
        AND p21_view_prod_order_hdr.complete = 'N'
        AND p21_view_prod_order_line.cancel = 'N'
"""
df = pd.read_sql(query, conn)

# ---------------------------------------------------------
# Data Prep & Filters
# ---------------------------------------------------------
df["expected_completion_date"] = pd.to_datetime(df["expected_completion_date"], errors="coerce")
df["production_machine"] = df["production_machine"].fillna("Unassigned")
df["scheduler_name"] = df["scheduler_name"].fillna("Unknown")

# Keep an uncapped, pre-slider copy for the Week Window table
df_base = df.copy()

# Pull in orders up to next week Friday
today = datetime.now().date()

days_until_friday = 4 - today.weekday()  # 0=Mon,4=Fri
if days_until_friday < 0:
    days_until_friday += 7  # wrap if today is Sat/Sun

max_allowed_date = today + timedelta(days=days_until_friday + 7)
df = df[df["expected_completion_date"].dt.date <= max_allowed_date]

# ---------------------------------------------------------
# Date Slider
# ---------------------------------------------------------
df = df.dropna(subset=["expected_completion_date"])
min_date = df["expected_completion_date"].min().to_pydatetime()
max_date = df["expected_completion_date"].max().to_pydatetime()

date_range = st.slider(
    "Select Expected Completion Date Range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="YYYY-MM-DD"
)

df = df[
    (df["expected_completion_date"] >= date_range[0])
    & (df["expected_completion_date"] <= date_range[1])
]

# ---------------------------------------------------------
# Aggregate for Bar Chart
# ---------------------------------------------------------
grouped = (
    df.groupby(["production_machine", "scheduler_name"], as_index=False)["extended_weight"]
    .sum()
)

schedulers = ["All"] + sorted(grouped["scheduler_name"].unique().tolist())
selected_scheduler = st.selectbox("Filter by Scheduler", schedulers)

if selected_scheduler != "All":
    filtered = grouped[grouped["scheduler_name"] == selected_scheduler]
else:
    filtered = grouped

# ---------------------------------------------------------
# Plotly Bar (Stacked)
# ---------------------------------------------------------
max_val = filtered["extended_weight"].max() if not filtered.empty else 0
fig = px.bar(
    filtered,
    x="production_machine",
    y="extended_weight",
    color="scheduler_name",
    barmode="stack",
    text_auto=".2s",
    title="Total Extended Weight by Production Machine & Scheduler",
    labels={
        "production_machine": "Production Machine",
        "extended_weight": "Total Extended Weight",
        "scheduler_name": "Scheduler"
    }
)
fig.update_yaxes(range=[0, max_val * 1.15 if max_val > 0 else 1])
fig.update_traces(textposition="auto")
fig.update_layout(
    xaxis_title="Production Machine",
    yaxis_title="Total Extended Weight",
    legend_title="Scheduler",
    bargap=0.25,
    plot_bgcolor="rgba(0,0,0,0)",
    hovermode="x unified",
    uniformtext_minsize=8,
    uniformtext_mode="hide",
)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# This Week Window Table
# ---------------------------------------------------------
st.subheader("📅 This Week Window (Mon–Fri)")

# Toggle to ADD the following week (not replace)
add_following_week = st.toggle("Show Following Week", value=False)

# Work from the uncapped, pre-slider data
wk_df = df_base.dropna(subset=["expected_completion_date"]).copy()

today_dt = datetime.now()
today_date = today_dt.date()

# Current week Mon–Fri
start_of_week = (today_dt - timedelta(days=today_dt.weekday()))
end_of_week = start_of_week + timedelta(days=4)

# If toggled, extend window through end of NEXT week (i.e., next Friday)
end_of_window = end_of_week + (timedelta(days=7) if add_following_week else timedelta(days=0))

# Slice the target multi-week window
week_df = wk_df[
    (wk_df["expected_completion_date"].dt.date >= start_of_week.date())
    & (wk_df["expected_completion_date"].dt.date <= end_of_window.date())
].copy()

# --- Compute late (past-due) carryover by machine (only dates < today) ---
past_due_df = wk_df[wk_df["expected_completion_date"].dt.date < today_date]
carryover_map = {}
carryover_orders_map = {}
if not past_due_df.empty:
    carryover_map = (
        past_due_df.groupby("production_machine")["extended_weight"]
        .sum()
        .to_dict()
    )
    carryover_orders_map = (
        past_due_df.groupby("production_machine")["prod_order_number"]
        .nunique()
        .to_dict()
    )

# Only add carryover rows once, mapped to today's date (so totals include carryover)
# (We do this whether or not following week is shown; today's still in the window.)
if carryover_map:
    today_stamp = pd.Timestamp(today_date)
    # Build a row per machine with total weight and correct number of dummy order numbers
    carry_rows_list = []
    for machine, weight in carryover_map.items():
        order_count = carryover_orders_map.get(machine, 0)
        # create one row per late order so distinct count == number of late orders
        for i in range(order_count):
            carry_rows_list.append({
                "production_machine": machine,
                "expected_completion_date": today_stamp,
                "extended_weight": weight / max(order_count, 1),  # evenly split for totals to still sum up
                "prod_order_number": f"late_{machine}_{i+1}",
                "scheduler_name": "Past-due carryover"
            })
    carry_rows = pd.DataFrame(carry_rows_list)
    # Optional label column to indicate provenance if you want to keep it
    if "scheduler_name" in week_df.columns and "scheduler_name" not in carry_rows.columns:
        carry_rows["scheduler_name"] = "Past-due carryover"
    week_df = pd.concat([week_df, carry_rows], ignore_index=True)

# Create explicit date for grouping
week_df["completion_date"] = week_df["expected_completion_date"].dt.date

# Group and aggregate by machine + date
agg_funcs = {
    "extended_weight": "sum",
    "prod_order_number": pd.Series.nunique
}

week_summary = (
    week_df.groupby(["production_machine", "completion_date"], as_index=False)
    .agg(agg_funcs)
    .rename(columns={"prod_order_number": "order_count"})
    .sort_values(["production_machine", "completion_date"])
)

# --- Pretty display for today's row: show "(X from late)" if applicable ---
def display_with_carry(row):
    val = row["extended_weight"]
    if row["completion_date"] == today_date:
        late = float(carryover_map.get(row["production_machine"], 0.0))
        if late > 0:
            return f"{val:.2f} ({late:.2f} from late)"
    return f"{val:.2f}"

def display_order_count_with_carry(row):
    val = int(row["order_count"])
    if row["completion_date"] == today_date:
        late_orders = carryover_orders_map.get(row["production_machine"], 0)
        if late_orders > 0:
            return f"{val} ({late_orders} from late)"
    return str(val)

week_summary["extended_weight_display"] = week_summary.apply(display_with_carry, axis=1)
week_summary["order_count_display"] = week_summary.apply(display_order_count_with_carry, axis=1)

# Dropdown filter by machine
machines = ["All"] + sorted(week_summary["production_machine"].unique().tolist())
selected_machine = st.selectbox("Filter by Machine (This Week Window)", machines, key="week_machine_filter")

# Apply machine filter
week_filtered = week_summary if selected_machine == "All" else week_summary[week_summary["production_machine"] == selected_machine]

# Show only the display column so the cell reads "total (late)" on today's date
week_to_show = (
    week_filtered[[
        "production_machine",
        "completion_date",
        "extended_weight_display",
        "order_count_display"
    ]]
    .rename(columns={
        "extended_weight_display": "extended_weight",
        "order_count_display": "order_count"
    })
)

st.dataframe(week_to_show, use_container_width=True)
