#!/usr/bin/env python3
"""
CATIA BOM extractor — fixed for FastAPI integration.
Generates CSV, XLSX, PDF and returns correct /downloads/ URLs.
Uses win32com.client directly for reliability.
"""

import argparse
import json
from pathlib import Path
import csv
import sys
import time
import traceback

try:
    import win32com.client
    HAS_COM = True
except ImportError:
    HAS_COM = False

# ===========================
# GLOBAL PATHS
# ===========================
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / ".." / "downloads"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR = OUTPUTS_DIR.resolve()


# Excel / PDF Support
try:
    import pandas as pd
    HAS_PANDAS = True
except:
    HAS_PANDAS = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except:
    HAS_REPORTLAB = False


def fallback_bom(path: Path):
    base = path.stem
    return [
        {"Item": 1, "PartNumber": f"{base}-001", "Description": "Main assembly (Simulated)", "Qty": 1, "Mass (kg)": 1.5, "Volume (m3)": 0.002},
        {"Item": 2, "PartNumber": f"{base}-002", "Description": "Bolt M6x20 (Simulated)", "Qty": 8, "Mass (kg)": 0.05, "Volume (m3)": 0.0001},
    ]


def write_csv(rows, out_csv):
    if rows:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def write_xlsx(rows, out_xlsx):
    if rows and HAS_PANDAS:
        pd.DataFrame(rows).to_excel(out_xlsx, index=False)


def write_pdf(rows, out_pdf):
    if not rows or not HAS_REPORTLAB:
        return
    c = canvas.Canvas(str(out_pdf), pagesize=letter)
    w, h = letter
    y = h - 40
    
    if rows:
        keys = list(rows[0].keys())
        c.setFont("Helvetica-Bold", 8)
        header = " | ".join(keys)
        c.drawString(20, y, header)
        y -= 20
        c.setFont("Helvetica", 8)

        for r in rows:
            line = " | ".join(str(r.get(k, ""))[:20] for k in keys)
            c.drawString(20, y, line)
            y -= 12
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 8)
                y = h - 40
    c.save()


# ===========================
# RECURSIVE BOM (COM)
# ===========================
def traverse_bom(product, rows, spa_workbench, level=0):
    """Recursive BOM extraction via COM."""
    
    try:
        children = product.Products
        count = children.Count
    except:
        return

    for i in range(1, count + 1):
        try:
            item = children.Item(i)
            
            # Get Reference Product (The actual Part/SubAssembly file)
            try: ref = item.ReferenceProduct
            except: ref = item
            
            part_number = ""
            try: part_number = ref.PartNumber
            except: part_number = item.PartNumber # Fallback to instance name if ref fails
            
            description = ""
            try: description = ref.DescriptionRef
            except: pass
            
            # --- Properties (Mass, Volume) ---
            mass = 0.0
            volume = 0.0
            
            # Mass/Volume from generic Measurable (Inertia)
            if spa_workbench:
                try:
                    # Measuring the Reference typically gives the Part properties
                    measurable = spa_workbench.GetMeasurable(ref)
                    mass = measurable.Mass
                    volume = measurable.Volume
                except:
                    # Fallback to Analyze object
                    try:
                        mass = ref.Analyze.Mass
                        volume = ref.Analyze.Volume
                    except: pass
            
            # Rounding
            mass = round(mass, 4)
            volume = round(volume, 6)
            
            # Add Row
            rows.append({
                "Item": len(rows) + 1,
                "PartNumber": part_number,
                "Description": description,
                "Qty": 1, 
                "Mass (kg)": mass,
                "Volume (m3)": volume
            })
            
            # Recurse
            if hasattr(ref, "Products") and ref.Products.Count > 0:
                traverse_bom(ref, rows, spa_workbench, level+1)

        except Exception as e:
            # print(f"Error processing item {i}: {e}", file=sys.stderr)
            pass


# ===========================
# MAIN
# ===========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    input_path = Path(args.input).resolve() # Absolute path
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    start = time.time()
    used_fallback = False

    if HAS_COM:
        try:
            # Connect to CATIA
            app = win32com.client.Dispatch("CATIA.Application")
            app.Visible = True 
            app.DisplayFileAlerts = False # Suppress popups

            # Open Document
            print(f"Opening: {input_path}...", file=sys.stderr)
            doc = app.Documents.Open(str(input_path))
            
            product = doc.Product
            
            # CRITICAL: Force Design Mode to load geometry for mass props
            try:
                product.ApplyWorkMode(1) # 1 = DESIGN_MODE
            except:
                print("Warning: Could not switch to Design Mode.", file=sys.stderr)
            
            # Get SPAWorkbench for measurements
            spa = None
            try:
                spa = doc.GetWorkbench("SPAWorkbench")
            except: pass

            # --- Extract Root ---
            # Root properties can be tricky, try best effort
            root_pn = product.PartNumber
            root_desc = getattr(product, "DescriptionRef", "")
            root_mass = 0.0
            root_vol = 0.0
            if spa:
                try:
                    measurable = spa.GetMeasurable(product)
                    root_mass = measurable.Mass
                    root_vol = measurable.Volume
                except: pass
            
            rows.append({
                "Item": 1,
                "PartNumber": root_pn,
                "Description": root_desc,
                "Qty": 1,
                "Mass (kg)": round(root_mass, 4),
                "Volume (m3)": round(root_vol, 6)
            })

            # --- Traverse Children ---
            traverse_bom(product, rows, spa)
            
            # doc.Close() 
            
        except Exception:
            print("CATIA Extraction Failed:", file=sys.stderr)
            traceback.print_exc()
            used_fallback = True
            rows = fallback_bom(input_path)
    else:
        print("win32com not found.", file=sys.stderr)
        used_fallback = True
        rows = fallback_bom(input_path)

    if not rows:
        used_fallback = True
        rows = fallback_bom(input_path)
        
    # Aggregate Duplicates (Optional improvement)
    # Group by PartNumber and Sum Qty?
    # For now, user asked for full extraction, let's keep flattened list or
    # implement simple condensation:
    
    unique_rows = {}
    ordered_keys = []
    
    for r in rows:
        key = r["PartNumber"]
        if not key: key = f"Unknown-{r['Item']}"
        
        if key in unique_rows:
            unique_rows[key]["Qty"] += 1
        else:
            unique_rows[key] = r
            ordered_keys.append(key)
            
    final_rows = [unique_rows[k] for k in ordered_keys]
    
    # Re-index Item numbers
    for idx, r in enumerate(final_rows):
        r["Item"] = idx + 1

    # File Naming
    stem = "Bill_of_materials"
    csv_path = out_dir / f"{stem}.csv"
    xlsx_path = out_dir / f"{stem}.xlsx"
    pdf_path = out_dir / f"{stem}.pdf"

    write_csv(final_rows, csv_path)
    write_xlsx(final_rows, xlsx_path)
    write_pdf(final_rows, pdf_path)

    def to_web(p: Path):
        # Assumes /downloads mount
        return f"/downloads/{p.name}"

    print(json.dumps({
        "mode": "bom",
        "ok": True,
        "files": {
            "csv": to_web(csv_path),
            "xlsx": to_web(xlsx_path),
            "pdf": to_web(pdf_path)
        },
        "from_catia": not used_fallback,
        "elapsed_s": round(time.time() - start, 2)
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
