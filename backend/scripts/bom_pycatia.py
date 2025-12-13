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
        {"Item": 1, "PartNumber": f"{base}-001", "Description": "Main assembly (Simulated)", "Qty": 1, "Material": "AL", "Mass (kg)": 1.5, "Volume (m3)": 0.002},
        {"Item": 2, "PartNumber": f"{base}-002", "Description": "Bolt M6x20 (Simulated)", "Qty": 8, "Material": "Steel", "Mass (kg)": 0.05, "Volume (m3)": 0.0001},
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
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, " | ".join(keys))
        y -= 20
        c.setFont("Helvetica", 10)

        for r in rows:
            line = " | ".join(str(r.get(k, "")) for k in keys)
            c.drawString(40, y, line)
            y -= 14
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = h - 40
    c.save()


# ===========================
# RECURSIVE BOM (COM)
# ===========================
# ===========================
# RECURSIVE BOM (COM)
# ===========================
def extract_product_recursive(prod, rows, get_props_func, level=0):
    """Recursive BOM extraction via COM."""
    
    try:
        children = prod.Products
        count = children.Count
    except:
        return

    for i in range(1, count + 1):
        try:
            item = children.Item(i)
            # ReferenceProduct
            try: ref = item.ReferenceProduct
            except: ref = item
            
            pn = ""
            try: pn = ref.PartNumber
            except: pass
            
            desc = ""
            try: desc = ref.DescriptionRef
            except: pass 
            
            # Use Helper passing BOTH Instance (item) and Reference (ref)
            mat, mass, vol = get_props_func(ref, item)
            
            rows.append({
                "Item": len(rows) + 1,
                "PartNumber": pn,
                "Description": desc,
                "Qty": 1,
                "Material": mat,
                "Mass (kg)": mass,
                "Volume (m3)": vol
            })
            
            # Recurse
            if ref.Products.Count > 0:
                extract_product_recursive(ref, rows, get_props_func, level+1)

        except Exception as e:
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
            
            # Material Manager (Global)
            manager = None
            try: manager = app.GetItem("CATIAMaterialManager")
            except: pass

            # Open Document
            print(f"Opening: {input_path}...", file=sys.stderr)
            doc = app.Documents.Open(str(input_path))
            
            # Extract
            product = doc.Product
            
            # Helper for properties
            def get_props(prod_ref, prod_inst=None):
                mat = ""
                mass = 0.0
                vol = 0.0
                
                # 1. UserRefProperties (Legacy)
                try:
                    props = prod_ref.UserRefProperties
                    for j in range(1, props.Count + 1):
                        p = props.Item(j)
                        if "material" in p.Name.lower():
                            mat = str(p.Value)
                            break
                except: pass
                
                # 2. CATIAMaterialManager
                if not mat and manager:
                    # A. Check Instance (if provided)
                    if prod_inst:
                        try:
                            oMat = manager.GetMaterialOnProduct(prod_inst)
                            if oMat: mat = oMat.Name
                        except: pass
                    
                    # B. Check Reference (if not found on instance)
                    if not mat:
                        try:
                            oMat = manager.GetMaterialOnProduct(prod_ref)
                            if oMat: mat = oMat.Name
                        except: pass
                    
                    # C. Check Part/Body (if Reference is a Part)
                    if not mat:
                        try:
                            parent_doc = prod_ref.Parent
                            if hasattr(parent_doc, "Part"):
                                part = parent_doc.Part
                                # Body
                                try:
                                    oMat = manager.GetMaterialOnBody(part.MainBody)
                                    if oMat: mat = oMat.Name
                                except: pass
                                # Part
                                if not mat:
                                    try:
                                        oMat = manager.GetMaterialOnPart(part)
                                        if oMat: mat = oMat.Name
                                    except: pass
                                
                                # D. Parameter Fallback (Inside Part)
                                if not mat and "part" in locals():
                                    try:
                                        params = part.Parameters
                                        for k in range(1, params.Count + 1):
                                            pm = params.Item(k)
                                            if pm.Name.split("\\")[-1].lower() == "material":
                                                try: mat = str(pm.ValueAsString())
                                                except: mat = str(pm.Value)
                                                break
                                    except: pass
                        except: pass

                # Mass / Volume (Inertia)
                try:
                    spa = doc.GetWorkbench("SPAWorkbench")
                    # Try measuring instance first, else reference
                    target = prod_inst if prod_inst else prod_ref
                    measurable = spa.GetMeasurable(target)
                    mass = measurable.Mass # kg
                    vol = measurable.Volume # m3
                except:
                    try:
                        mass = prod_ref.Analyze.Mass
                        vol = prod_ref.Analyze.Volume
                    except: pass
                
                return mat, round(mass, 4), round(vol, 6)

            # Add root item (Reference only, no Instance)
            root_mat, root_mass, root_vol = get_props(product, None)
            rows.append({
                "Item": 1, 
                "PartNumber": product.PartNumber, 
                "Description": getattr(product, "DescriptionRef", "") or "Root", 
                "Qty": 1, 
                "Material": root_mat,
                "Mass (kg)": root_mass,
                "Volume (m3)": root_vol
            })
            
            # Extract children
            extract_product_recursive(product, rows, get_props)
            
            # doc.Close() # User requested to see it open? "THAT FILE NEED TO OPEN IN CATIA... AND LATER... SAVED". 
            # We keeps it open or close? Usually strictly better to Keep Open if user wants to see. 
            # I will leave it open.
            
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

    # File Naming
    stem = input_path.stem.replace(" ", "_").replace("-", "_")
    csv_path = out_dir / f"{stem}_BOM.csv"
    xlsx_path = out_dir / f"{stem}_BOM.xlsx"
    pdf_path = out_dir / f"{stem}_BOM.pdf"

    write_csv(rows, csv_path)
    write_xlsx(rows, xlsx_path)
    write_pdf(rows, pdf_path)

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
