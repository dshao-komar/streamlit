import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Production Output Dashboard", layout="wide")

# Path relative to repo root
data_path = Path("data/September Averages.xlsx")
sheet_name = "Daily by Shifts"

st.title("🏭 Production Output Dashboard")
st.write("Shift Date Range: September 4-25, 2025")

try:
    df = pd.read_excel(data_path, sheet_name=sheet_name, engine="openpyxl")
except FileNotFoundError:
    st.error("❌ Could not find 'data/September Averages.xlsx'. Make sure it's included in the repo.")
    st.stop()
except Exception as e:
    st.error(f"❌ Error reading Excel file: {e}")
    st.stop()

# -----------------------------------------------------------
# CLEANING & FILTERING
# -----------------------------------------------------------
# Ensure consistent column names
df.columns = df.columns.str.strip()

required_cols = ["Machine Name", "Shift", "Date", "Total Produced (LB)"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing expected columns: {missing}")
    st.stop()

# Drop rows where Total Produced (LB) is blank or NaN
df = df.dropna(subset=["Total Produced (LB)"])
df["Total Produced (LB)"] = pd.to_numeric(df["Total Produced (LB)"], errors="coerce")
df = df.dropna(subset=["Total Produced (LB)"])

# st.write(f"Data rows after filtering: **{len(df)}**")
# st.dataframe(df.head(20))

# -----------------------------------------------------------
# AGGREGATION
# -----------------------------------------------------------
agg_df = (
    df.groupby("Machine Name", dropna=False)["Total Produced (LB)"]
    .agg(["count", "mean", "max", "min"])
    .reset_index()
    .rename(columns={
        "count": "# Shifts",
        "mean": "Avg Daily LB Produced",
        "max": "Most Productive Day",
        "min": "Least Productive Day"
    })
)

agg_df = agg_df.sort_values(by="Avg Daily LB Produced", ascending=False)
machines = agg_df["Machine Name"].tolist()

# -----------------------------------------------------------
# CHART 1: Bar by Machine, colored by Shift (avg per shift)
# -----------------------------------------------------------
st.markdown("---")
st.header("Chart 1: Average Daily Production by Machine and Shift")

# Compute mean by Machine + Shift
shift_df = (
    df.groupby(["Machine Name", "Shift"])["Total Produced (LB)"]
    .mean()
    .reset_index()
    .rename(columns={"Total Produced (LB)": "Avg Daily LB Produced"})
)

# Sort by total avg per machine
sort_order = (
    shift_df.groupby("Machine Name")["Avg Daily LB Produced"].mean().sort_values(ascending=False).index.tolist()
)
shifts = sorted(shift_df["Shift"].unique())

fig1 = go.Figure()
for sh in shifts:
    d = shift_df[shift_df["Shift"] == sh].set_index("Machine Name").reindex(sort_order)
    fig1.add_bar(
        name=str(sh),
        x=sort_order,
        y=d["Avg Daily LB Produced"],
        hovertemplate=(
            "<b>%{x}</b><br>"
            f"Shift: {sh}<br>"
            "Avg Daily LB: %{y:.0f}<extra></extra>"
        ),
    )

fig1.update_layout(
    barmode="group",  # or "stack" if you prefer stacking
    xaxis_title="Machine",
    yaxis_title="Avg Daily LB Produced",
    legend_title="Shift",
    height=500,
    margin=dict(l=20, r=20, t=40, b=40),
)
st.plotly_chart(fig1, use_container_width=True)

# -----------------------------------------------------------
# CHART 2: Bar by Machine (overall AVG with error bars)
# -----------------------------------------------------------
st.markdown("---")
st.header("Chart 2: Average vs Most/Least Productive Day by Machine")

upper = (agg_df["Most Productive Day"] - agg_df["Avg Daily LB Produced"]).clip(lower=0)
lower = (agg_df["Avg Daily LB Produced"] - agg_df["Least Productive Day"]).clip(lower=0)

fig2 = go.Figure()
fig2.add_bar(
    x=machines,
    y=agg_df["Avg Daily LB Produced"],
    error_y=dict(type="data", array=upper, arrayminus=lower, visible=True),
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Avg Daily LB: %{y:.0f}<br>"
        "Max: %{customdata[0]:.0f}<br>"
        "Min: %{customdata[1]:.0f}<extra></extra>"
    ),
    customdata=np.stack(
        (agg_df["Most Productive Day"], agg_df["Least Productive Day"]), axis=-1
    ),
)

fig2.update_layout(
    xaxis_title="Machine",
    yaxis_title="Avg Daily LB Produced",
    showlegend=False,
    height=480,
    margin=dict(l=20, r=20, t=40, b=40),
)
st.plotly_chart(fig2, use_container_width=True)

# -----------------------------------------------------------
# Aggregated summary table
# -----------------------------------------------------------
st.markdown("---")
st.subheader("Aggregated Summary by Machine")
st.dataframe(
    agg_df[["Machine Name", "Avg Daily LB Produced", "# Shifts", "Most Productive Day", "Least Productive Day"]],
    use_container_width=True,
)
