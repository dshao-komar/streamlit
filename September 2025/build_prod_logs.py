import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
import pandas as pd
from rapidfuzz import fuzz

# ---------------- Debug helper (machine detection only) ----------------
def dbg(msg: str):
    print(f"[MACH-DEBUG] {msg}")

# ---------------- Normalization for fuzzy ----------------
def normalize(s: str) -> str:
    s2 = s.lower()
    s2 = re.sub(r"[_\-]+", " ", s2)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2

def flex(token: str) -> str:
    """
    Turn a token like 'CUTTER # 2' into a forgiving regex that allows
    spaces/hyphens/underscores to float. Also makes '#' spacing optional.

    NOTE: We do NOT use re.sub with a replacement containing \s here,
    to avoid 'bad escape \\s' issues. We build the pattern directly.
    """
    token = token.strip()
    if not token:
        return ""
    parts = re.split(r"[ \-_]+", token)                 # split on separators
    parts_esc = [re.escape(p) for p in parts if p]      # escape each literal
    pattern = r"[\s\-_]*".join(parts_esc)               # join with flexible class
    pattern = pattern.replace(r"\#", r"\s*#\s*")        # optional spaces around '#'
    return pattern

# ---------------- Build page text from lines (with enhanced debug) ----------------
def page_text_from_lines(analyze_result: dict):
    """
    Returns dict[pageNumber] = concatenated line content for that page.
    Also logs the first 10 raw line.contents for each page.
    """
    pages = analyze_result.get("pages") or []
    out = {}
    for p in pages:
        pg = p.get("pageNumber")
        lines = p.get("lines") or []
        line_texts = [(ln.get("content") or "").strip() for ln in lines if ln.get("content")]
        text = " ".join(line_texts)
        out[pg] = text

        # ---- DEBUG: show first 10 raw line contents verbatim ----
        dbg(f"Page {pg}: lines={len(line_texts)}, text_len={len(text)}")
        first10 = line_texts[:10]
        for i, t in enumerate(first10, 1):
            dbg(f"  line[{i}]: {repr(t)}")
        if len(line_texts) > 10:
            dbg(f"  ... ({len(line_texts) - 10} more lines)")
    return out

# ---------------- Hand-coded machine list and variant patterns ----------------
def build_machine_catalog():
    """
    Hard-coded machine display names + regex variants for messy OCR.
    Returns:
      display_names: list[str]
      regex_variants: dict[str, set[str]]  (each value is ready-to-use regex)
    """
    display_names = [
        "AW1","Cutter1","Cutter2","Die-cutter","Jennerjahn","Pc1","Pc2","Pc3","Pc5","Sheeter1","Sheeter2"
    ]

    variants = defaultdict(set)
    for disp in display_names:
        variants[disp].add(disp)

        low = disp.lower()

        # Per-family extras (unescaped, we will flex() later)
        if low.startswith("cutter"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                variants[disp].update({
                    f"CUTTER {n}", f"CUTTER #{n}", f"CUTTER_{n}", f"CUTTER-{n}",
                    f"Cutter {n}", f"Cutter #{n}", f"Cutter_{n}", f"Cutter-{n}",
                    f"CUTTER#{n}", f"Cutter#{n}"
                })

        if low.startswith("pc"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                variants[disp].update({f"PC{n}", f"PC {n}", f"PC_{n}", f"PC-{n}", f"Pc{n}", f"Pc {n}"})

        if low.startswith("sheeter"):
            m = re.search(r"(\d+)$", low)
            if m:
                n = m.group(1)
                variants[disp].update({f"SHEETER{n}", f"SHEETER {n}", f"SHEETER_{n}", f"Sheeter {n}"})

        if low == "die-cutter":
            variants[disp].update({"DIE-CUTTER","DIE CUTTER","Die Cutter","Die-Cutter"})

        if low == "aw1":
            variants[disp].update({"AW1","AW 1","AW-1","AW_1"})

        if low == "jennerjahn":
            variants[disp].add("JENNERJAHN")

        # Convert raw variants into forgiving regexes
        variants[disp] = {flex(v) for v in variants[disp] if v}

    # Make values deterministic
    regex_variants = {k: sorted(v) for k, v in variants.items()}
    return display_names, regex_variants

# ---------------- Fuzzy + regex machine detection per page ----------------
def detect_machine_per_page(page_text: dict, display_order, regex_variants, fuzzy_threshold=85):
    """
    For each page:
      1) Try regex variants of each display name against the raw page text (case-insensitive).
      2) If no regex hit, fuzzy rank (RapidFuzz WRatio) each display name and keep the best if >= threshold.
    Returns dict[pageNumber] = display_name
    """
    page_to_machine = {}
    for pg in sorted(page_text.keys()):
        raw = page_text[pg] or ""
        norm_txt = normalize(raw)

        # 1) Regex pass
        chosen = None
        for disp in display_order:
            for rx in regex_variants.get(disp, []):
                if re.search(rx, raw, flags=re.IGNORECASE):
                    chosen = disp
                    dbg(f"Page {pg}: REGEX matched '{disp}' via /{rx}/")
                    break
            if chosen:
                break

        # 2) Fuzzy fallback
        if not chosen and norm_txt:
            best_disp, best_score = None, -1
            for disp in display_order:
                # choose the max score across all its variants
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

# ---------------- Table conversion (quiet) ----------------
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

    # header = first non-empty row
    header_idx = None
    for i, row in df.iterrows():
        if any(str(x).strip() for x in row.tolist()):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()

    header = df.iloc[header_idx].astype(str).str.strip().tolist()
    # unique headers
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

    # drop fully-empty cols/rows
    empty_cols = body.apply(lambda col: col.astype(str).str.strip().eq("").all())
    body = body.loc[:, ~empty_cols]
    body = body[~body.apply(lambda row: row.astype(str).str.strip().eq("").all(), axis=1)]
    return body.reset_index(drop=True)

def collect_tables_by_page(analyze_result: dict):
    tables = analyze_result.get("tables", []) or []
    page_tables = defaultdict(list)
    for tbl in tables:
        pgs = set()
        for br in tbl.get("boundingRegions", []):
            pg = br.get("pageNumber")
            if pg:
                pgs.add(pg)
        if not pgs:
            pgs = {1}
        df_tbl = table_to_dataframe(tbl)
        for pg in sorted(pgs):
            page_tables[pg].append(df_tbl)
    return page_tables

def sanitize_sheet_name(name: str) -> str:
    s = re.sub(r'[^A-Za-z0-9 _\-#]', '_', name).strip()
    return s[:31] if s else "Sheet"

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser(description="3-tab Excel from Azure DI JSON; machine naming from pages[*].lines via regex+fuzzy (manual machine list).")
    ap.add_argument("--json", required=True, help="Path to Azure DI JSON")
    ap.add_argument("--out", default="production_logs_three_tabs_named.xlsx", help="Output Excel file")
    ap.add_argument("--fuzzy", type=int, default=85, help="Fuzzy similarity threshold (0-100)")
    args = ap.parse_args()

    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)
    ar = data.get("analyzeResult", {})

    # Build machine catalog (manual)
    display_order, regex_variants = build_machine_catalog()
    dbg(f"Loaded machines: {display_order}")

    # Build per-page text from lines + debug first 10 lines
    per_page_text = page_text_from_lines(ar)

    # Detect machine per page (regex first, then fuzzy)
    page_to_machine = detect_machine_per_page(per_page_text, display_order, regex_variants, fuzzy_threshold=args.fuzzy)

    # Tables → Excel (quiet)
    page_tables = collect_tables_by_page(ar)
    selected_pages = sorted(page_tables.keys())[:3]

    with pd.ExcelWriter(args.out, engine="xlsxwriter") as writer:
        if not selected_pages:
            pd.DataFrame({"note": ["No tables detected."]}).to_excel(writer, index=False, sheet_name="No Tables")
        else:
            for pg in selected_pages:
                sheet_name = sanitize_sheet_name(page_to_machine.get(pg, f"Page {pg}"))
                dfs = [d for d in page_tables.get(pg, []) if d is not None and not d.empty]
                if not dfs:
                    pd.DataFrame({"note": [f"No non-empty tables on page {pg}."]}).to_excel(writer, index=False, sheet_name=sheet_name)
                    continue
                startrow = 0
                pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet_name)
                for df_tbl in dfs:
                    df_tbl.to_excel(writer, index=False, sheet_name=sheet_name, startrow=startrow)
                    startrow += len(df_tbl) + 2

    print(f"Excel written: {Path(args.out).resolve()}")

if __name__ == "__main__":
    main()
