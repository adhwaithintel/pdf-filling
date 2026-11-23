"""
Run ONCE per template.  Reads a flat (non-fillable) PDF and writes a schema:
    field name -> {page, bbox of the cell where the VALUE goes}
It finds filled cells (rectangles), reads the label words inside each cell,
then decides where the value goes:
   * a cell directly to the RIGHT with same top/bottom  -> row-style field
   * a cell directly BELOW with same x-range            -> header-style field
   * neither                                            -> section header (skipped)
Usage: python extract_template_schema.py TSOW_Template.pdf tsow_schema.json
"""
import sys, json
import pdfplumber

TOL = 1.5
BORDER = (0.549, 0.6078, 0.6471)          # thin border strips in this template


def close(a, b): return abs(a - b) <= TOL


def build_schema(pdf_path):
    schema = {"pages": [], "fields": {}}
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            schema["pages"].append({"page": pno, "width": float(page.width),
                                    "height": float(page.height)})
            # real cells = filled rects, not the page background, not 1px borders
            cells = [r for r in page.rects
                     if (r["x1"] - r["x0"]) > 20 and (r["bottom"] - r["top"]) > 10
                     and (r["x1"] - r["x0"]) < page.width - 5
                     and tuple(round(c, 3) for c in (r.get("non_stroking_color") or ())) != BORDER]
            words = page.extract_words(keep_blank_chars=False)

            def label_of(c):
                ws = [w for w in words
                      if w["x0"] >= c["x0"] - 1 and w["x1"] <= c["x1"] + 1
                      and w["top"] >= c["top"] - 1 and w["bottom"] <= c["bottom"] + 1]
                ws.sort(key=lambda w: (round(w["top"]), w["x0"]))
                return " ".join(w["text"] for w in ws).strip()

            for c in cells:
                label = label_of(c)
                if not label:
                    continue
                right = next((o for o in cells if o is not c and close(o["x0"], c["x1"])
                              and close(o["top"], c["top"]) and close(o["bottom"], c["bottom"])
                              and not label_of(o)), None)
                below = next((o for o in cells if o is not c and close(o["top"], c["bottom"])
                              and close(o["x0"], c["x0"]) and close(o["x1"], c["x1"])
                              and not label_of(o)), None)
                tgt, kind = (right, "right") if right else (below, "below") if below else (None, None)
                if tgt is None:
                    continue                      # section header like "Key Contacts"
                schema["fields"][label] = {
                    "page": pno, "placement": kind,
                    "bbox": [round(tgt["x0"], 1), round(tgt["top"], 1),
                             round(tgt["x1"], 1), round(tgt["bottom"], 1)],   # top-left origin
                }
    return schema


if __name__ == "__main__":
    s = build_schema(sys.argv[1])
    json.dump(s, open(sys.argv[2], "w"), indent=2)
    print(f"{len(s['fields'])} fields -> {sys.argv[2]}")
    for k, v in s["fields"].items():
        print(f"  {k:22s} p{v['page']} {v['placement']:5s} {v['bbox']}")
