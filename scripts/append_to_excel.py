import pandas as pd
from openpyxl import load_workbook
from pathlib import Path

CSV_PATH = Path("data/daily_output_log.csv")
XLSX_PATH = Path("data/September Averages.xlsx")
SHEET_NAME = "Daily by Shifts"

def append_new_rows():
    csv_df = pd.read_csv(CSV_PATH)
    wb = load_workbook(XLSX_PATH)
    ws = wb[SHEET_NAME]

    # Load existing sheet data into DataFrame
    existing_df = pd.DataFrame(ws.values)
    header = existing_df.iloc[0]
    existing_df = pd.DataFrame(existing_df.values[1:], columns=header)

    # Find new rows (based on full record uniqueness)
    merged = csv_df.merge(existing_df, how="left", indicator=True)
    new_rows = merged[merged["_merge"] == "left_only"].drop(columns="_merge")

    if new_rows.empty:
        print("No new rows to append.")
        return False

    # Append new rows to worksheet
    for _, row in new_rows.iterrows():
        ws.append(list(row))

    wb.save(XLSX_PATH)
    print(f"Appended {len(new_rows)} new rows.")
    return True

if __name__ == "__main__":
    append_new_rows()
