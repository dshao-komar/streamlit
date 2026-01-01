import os
from dotenv import load_dotenv
import streamlit as st
import pyodbc
import pandas as pd

# Load .env values
load_dotenv()

st.title("SQL Server Dashboard")

uid = os.getenv("STREAMLIT_DB_USER")
pwd = os.getenv("STREAMLIT_DB_PASS")
server = "172.22.4.20,1433"
database = "P21"

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={server};DATABASE={database};UID={uid};PWD={pwd};"
)

conn = pyodbc.connect(conn_str)
df = pd.read_sql("SELECT TOP 10 * FROM prod_order_hdr", conn)
print(df.head())
