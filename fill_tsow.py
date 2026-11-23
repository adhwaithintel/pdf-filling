"""
Fill the flat TSOW template from the extraction JSON.
Method: draw text into an in-memory overlay PDF (ReportLab) and merge it on top
of the original template (pypdf).  Original design stays untouched.

Usage: python fill_tsow.py TSOW_Template.pdf tsow_schema.json data.json out.pdf
"""
import io, sys, json
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from xml.sax.saxutils import escape

PAD = 4                      # inner padding of a cell (pt)
MAX_FONT, MIN_FONT = 10, 5   # auto-shrink range
FONT = "Helvetica"


def to_text(value):
    """str | number | list | dict  ->  XML-safe paragraph markup."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "<br/>".join("&bull; " + escape(str(v)) for v in value if str(v).strip())
    if isinstance(value, dict):
        return "<br/>".join(f"<b>{escape(str(k))}:</b> {escape(str(v))}" for k, v in value.items())
    return escape(str(value)).replace("\n", "<br/>")


def fit_paragraph(markup, width, height):
    """Largest font size (MAX..MIN) whose wrapped text fits the box."""
    size = MAX_FONT
    while size >= MIN_FONT:
        style = ParagraphStyle("c", fontName=FONT, fontSize=size,
                               leading=size * 1.18, alignment=TA_LEFT)
        p = Paragraph(markup, style)
        _, h = p.wrap(width, height)
        if h <= height:
            return p, h, size, True
        size -= 0.5
    return p, h, MIN_FONT, False          # did not fit even at MIN_FONT


def fill(template, schema_path, data, out_path):
    schema = json.load(open(schema_path))
    # accept nested groups too: {"Key Contacts": {"Intel": ..}} -> flat
    flat = {}
    for k, v in data.items():
        if k not in schema["fields"] and isinstance(v, dict):
            flat.update(v)
        else:
            flat[k] = v
    norm = {k.strip().lower(): k for k in schema["fields"]}     # forgiving key match
    report = {"filled": [], "missing_in_pdf": [], "overflow": [], "empty": []}

    reader = PdfReader(template)
    buffers = {}                                                # page -> canvas
    for pinfo in schema["pages"]:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(pinfo["width"], pinfo["height"]))
        buffers[pinfo["page"]] = (c, buf, pinfo["height"])

    for key, value in flat.items():
        real = norm.get(key.strip().lower())
        if real is None:
            report["missing_in_pdf"].append(key)
            continue
        markup = to_text(value)
        if not markup.strip():
            report["empty"].append(real)
            continue
        f = schema["fields"][real]
        x0, top, x1, bottom = f["bbox"]
        w, h = (x1 - x0) - 2 * PAD, (bottom - top) - 2 * PAD
        p, ph, size, ok = fit_paragraph(markup, w, h)
        if not ok:
            report["overflow"].append(f"{real} (needs {ph:.0f}pt, has {h:.0f}pt)")
        c, _, H = buffers[f["page"]]
        # clip so overflowing text can never spill into neighbouring cells
        c.saveState()
        path = c.beginPath(); path.rect(x0, H - bottom, x1 - x0, bottom - top)
        c.clipPath(path, stroke=0, fill=0)
        p.drawOn(c, x0 + PAD, H - top - PAD - ph)               # PDF y-origin is bottom-left
        c.restoreState()
        report["filled"].append(f"{real} @ {size}pt")

    # clone the template into the writer first (required by pypdf >= 6/7)
    writer = PdfWriter(clone_from=template)
    for i, page in enumerate(writer.pages, 1):
        c, buf, _ = buffers[i]
        c.save(); buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
    with open(out_path, "wb") as fh:
        writer.write(fh)
    return report


if __name__ == "__main__":
    tpl, sch, data_json, out = sys.argv[1:5]
    rep = fill(tpl, sch, json.load(open(data_json)), out)
    print(json.dumps(rep, indent=2))
