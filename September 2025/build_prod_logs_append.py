import argparse
import json
import re
from pathlib import Path
from collections import defaultdict, OrderedDict

import pandas as pd
from rapidfuzz import fuzz

# ---------------- Debug helper (machine detection + header checks only) ------------
def dbg(msg: str):
    print(f"[MACH-DEBUG] {msg}")

# ---------------- Normalization for fuzzy -----------------------------------------
def normalize(s: str) -> str:
    s2 = s.lower()
    s2 = re.sub(r"[_\-]+", " ", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2

# ---------------- Build page text from lines (debug shows first 10 lines) ----------
def page_text_from_lines(analyze_result: dict):
    pages = analyze_result.get("pages") or []
    out = {}
    for p in pages:
        pg = p.get("pageNumber")
        lines = p.get("lines") or []
        line_texts = [(ln.get("content") or "").strip() for ln in lines if ln.get("content")]
        text = " ".join(line_texts)
        out[pg] = text

        dbg(f"Page {pg}: lines={len(line_texts)}, text_len={len(text)}")
        for i, t in enumerate(line_texts[:10], 1):
            dbg(f"  line[{i}]: {repr(t)}")
        if len(line_texts) > 10:
            dbg(f"  ... ({len(line_texts) - 10} more lines)")
    return out

# ---------------- Hand-coded machine list & flexible regex variants ----------------
def flex(token: str) -> str:
    """
    Turn 'CUTTER # 2' into a forgiving regex that allows spaces/hyphens/underscores.
    Also make '#' spacing optional. (No re.sub replacement with \s to avoid Py3.13 issues.)
    """
    token = token.strip()
    if not token:
        return ""
    parts = re.split(r"[ \-_]+", token)
    parts_esc = [re.escape(p) for p in parts if p]
    pattern = r"[\s\-_]*".join(parts_esc)
    pattern = pattern.replace(r"\#", r"\s*#\s*")
    return pattern

def build_machine_catalog():
    """
    Hard-coded machines + regex variants for messy OCR.
    Returns:
      display_names (ordered list),
      regex_variants: dict[display_name] -> list of ready-to-use regex strings
    """
    display_names = [
        "AW1","Cutter1","Cutter2","Die-cutter","Jennerjahn",
        "Pc1","Pc2","Pc3","Pc5","Sheeter1","Sheeter2"
    ]

    raw_variants = defaultdict(set)
    for disp in display_names:
        raw_variants[disp].add(disp)
        low = disp.lower()

        if low.startswith("cutter"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                raw_variants[disp].update({
                    f"CUTTER {n}", f"CUTTER #{n}", f"CUTTER_{n}", f"CUTTER-{n}",
                    f"Cutter {n}", f"Cutter #{n}", f"Cutter_{n}", f"Cutter-{n}",
                    f"CUTTER#{n}", f"Cutter#{n}"
                })

        if low.startswith("pc"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                raw_variants[disp].update({f"PC{n}", f"PC {n}", f"PC_{n}", f"PC-{n}", f"Pc{n}", f"Pc {n}"})

        if low.startswith("sheeter"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                raw_variants[disp].update({f"SHEETER{n}", f"SHEETER {n}", f"SHEETER_{n}", f"Sheeter {n}"})

        if low == "die-cutter":
            raw_variants[disp].update({"DIE-CUTTER","DIE CUTTER","Die Cutter","Die-Cutter"})

        if low == "aw1":
            raw_variants[disp].update({"AW1","AW 1","AW-1","AW_1"})

        if low == "jennerjahn":
            raw_variants[disp].add("JENNERJAHN")

    regex_variants = {disp: sorted({flex(v) for v in raw_variants[disp] if v})
                      for disp in display_names}
    return display_names, regex_variants

# ---------------- Detect a machine per page (regex first, then fuzzy) --------------
def detect_machine_per_page(page_text: dict, display_order, regex_variants, fuzzy_threshold=85):
    page_to_machine = {}
    for pg in sorted(page_text.keys()):
        raw = page_text[pg] or ""
        norm_txt = normalize(raw)

        chosen = None
        # 1) Regex pass
        for disp in display_order:
            for rx in regex_variants.get(disp, []):
                if re.search(rx, raw, flags=re.IGNORECASE):
                    chosen = disp
                    dbg(f"Page {pg}: REGEX matched '{disp}' via /{rx}/")
                    break
            if chosen:
                break

        # 2) Fuzzy pass
        if not chosen and norm_txt:
            best_disp, best_score = None, -1
            for disp in display_order:
                score = max(fuzz.WRatio(normalize(v), norm_txt) for v in regex_variants.get(disp, [disp]))
                if score > best_score:
                    best_score, best_disp = score, disp
            dbg(f"Page {pg}: FUZZY best='{best_disp}' score={best_score}")
            if best_score >= fuzzy_threshold:
                chosen = best_disp

        if chosen:
            page_to_machine[pg] = chosen
        else:
            dbg(f"Page {pg}: no machine detected (regex+fuzzy).")
    dbg(f"Final page→machine mapping: {page_to_machine}")
    return page_to_machine

# ---------------- Azure DI table -> DataFrame (header from first non-empty row) ----
def table_to_dataframe(tbl):
    cells = tbl.get("cells", []) or []
    if not cells:
        return pd.DataFrame()
    max_row = max(c.get("rowIndex", 0) + c.get("rowSpan", 1) - 1 for c in cells)
    max_col = max(c.get("columnIndex", 0) + c.get("columnSpan", 1) - 1 for c in cells)
    grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for c in cells:
        r0 = c.get("rowIndex", 0)
        c0 = c.get("columnIndex", 0)
        txt = (c.get("content") or "").strip()
        grid[r0][c0] = txt
    df = pd.DataFrame(grid)

    # Header = first non-empty row
    header_idx = None
    for i, row in df.iterrows():
        if any(str(x).strip() for x in row.tolist()):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()

    header = df.iloc[header_idx].astype(str).str.strip().tolist()
    # Unique headers
    seen = {}
    cols = []
    for h in header:
        h2 = h if h else "col"
        seen[h2] = seen.get(h2, 0) + 1
        if seen[h2] > 1:
            h2 = f"{h2}_{seen[h2]}"
        cols.append(h2)

    body = df.iloc[header_idx + 1:].copy()
    body.columns = cols

    # Drop fully-empty cols/rows
    empty_cols = body.apply(lambda col: col.astype(str).str.strip().eq("").all())
    body = body.loc[:, ~empty_cols]
    body = body[~body.apply(lambda row: row.astype(str).str.strip().eq("").all(), axis=1)]
    return body.reset_index(drop=True)

# ---------------- Collect tables and APPEND per machine (no headers on repeats) ----
def sanitize_sheet_name(name: str) -> str:
    s = re.sub(r'[^A-Za-z0-9 _\-#]', '_', name).strip()
    return s[:31] if s else "Sheet"

def append_tables_by_machine(ar: dict, page_to_machine: dict, out_path: Path):
    tables = ar.get("tables", []) or []

    # Per-sheet state: track next startrow and the "first header count"
    sheet_state = {}  # name -> {"startrow": int, "first_header_cols": int|None}

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        for t_idx, tbl in enumerate(tables):
            # Which page is this table on (usually one)?
            pgs = {br.get("pageNumber") for br in tbl.get("boundingRegions", []) if br.get("pageNumber")}
            page = min(pgs) if pgs else 1

            df = table_to_dataframe(tbl)
            if df is None or df.empty:
                continue

            # Resolve sheet name by page's machine (fallback Page N)
            machine = page_to_machine.get(page, f"Page {page}")
            sheet = sanitize_sheet_name(machine)

            # Sheet state
            if sheet not in sheet_state:
                sheet_state[sheet] = {"startrow": 0, "first_header_cols": None}

            st = sheet_state[sheet]

            # Check header length consistency vs the first table on this sheet
            cur_cols = len(df.columns)
            if st["first_header_cols"] is None:
                st["first_header_cols"] = cur_cols
            else:
                if cur_cols != st["first_header_cols"]:
                    dbg(f"HEADER MISMATCH on sheet '{sheet}': first={st['first_header_cols']} vs table{t_idx}={cur_cols}")

            # First write for this sheet? include header; otherwise append w/o header
            include_header = (st["startrow"] == 0)

            # Ensure sheet exists before positioning
            if include_header and st["startrow"] == 0:
                pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet)

            # Write
            df.to_excel(
                writer,
                sheet_name=sheet,
                index=False,
                header=include_header,
                startrow=st["startrow"]
            )

            # Update next start row (+ blank row between tables)
            rows_written = len(df) + (1 if include_header else 0)
            st["startrow"] += rows_written + 1

    print(f"Excel written: {out_path.resolve()}")
    dbg(f"Sheets created: {list(sheet_state.keys())}")

# ---------------- Main -------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Append Azure DI tables per machine sheet; on repeats, add without headers and warn if header counts differ."
    )
    ap.add_argument("--json", required=True, help="Path to Azure DI JSON")
    ap.add_argument("--out", default="production_logs_by_machine.xlsx", help="Output Excel file")
    ap.add_argument("--fuzzy", type=int, default=85, help="Fuzzy similarity threshold (0-100)")
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)
    ar = data.get("analyzeResult", {})

    # 1) Detect machine per page (from lines)
    display_order, regex_variants = build_machine_catalog()
    per_page_text = page_text_from_lines(ar)
    page_to_machine = detect_machine_per_page(per_page_text, display_order, regex_variants, fuzzy_threshold=args.fuzzy)

    # 2) Append tables by machine (no headers on repeats)
    out_path = Path(args.out)
    append_tables_by_machine(ar, page_to_machine, out_path)

if __name__ == "__main__":
    main()
