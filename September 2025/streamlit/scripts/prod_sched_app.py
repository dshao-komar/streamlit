import streamlit as st
import pandas as pd
import pyodbc
from dotenv import load_dotenv
import os

# Load .env values
load_dotenv()

uid = os.getenv("STREAMLIT_DB_USER")
pwd = os.getenv("STREAMLIT_DB_PASS")
server = "172.22.4.20,1433"
database = "P21"

st.title("Prod Order Schedule")

# ---------------------------------------------------------
# SQL Connection
# ---------------------------------------------------------
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={server};DATABASE={database};UID={uid};PWD={pwd};"
)
conn = pyodbc.connect(conn_str)

query = """
    SELECT 
        p21_view_prod_order_hdr.prod_order_number,
        p21_view_prod_order_hdr.expected_completion_date,
        p21_view_prod_order_hdr.complete,
        p21_view_prod_order_line.item_id,
        prod_order_hdr_ud.production_machine,
        p21_view_prod_order_line.qty_to_make,
        p21_view_inv_loc.location_id,
        p21_view_inv_mast.item_desc,
        p21_view_inv_loc.product_group_id,
        p21_view_prod_order_line.unit_of_measure,
        p21_view_inv_mast.net_weight,
        p21_view_inv_mast.net_weight * p21_view_prod_order_line.qty_to_make         AS extended_weight,
        p21_view_prod_order_hdr.printed,
        p21_view_prod_order_hdr.comment,
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
    
    ORDER BY 
        p21_view_prod_order_hdr.expected_completion_date
      , prod_order_hdr_ud.production_machine
"""

df = pd.read_sql(query, conn)

st.dataframe(df)
