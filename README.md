# TSOW PDF Filler

Fills the **Intel AI ISV Partnerships TSOW** template (a flat, non-fillable PDF) from a JSON file produced by the information-extraction step.

Method: **overlay**. Text is drawn on a transparent page with ReportLab and merged onto the original template with pypdf, so the template design is never modified.

---

## 1. Project structure

```
tsow_project/
├── TSOW_Template.pdf          # original template (input)
├── tsow_schema.json           # field -> cell coordinates (generated once)
├── extract_template_schema.py # builds tsow_schema.json from the template
├── fill_tsow.py               # fills the template from a JSON file
├── data.json                  # extraction output (input)
├── sample_data.json           # example flat JSON for testing
├── requirements.txt
└── output.pdf                 # result (generated)
```

## 2. Setup

Requires **Python 3.9+**.

```bash
# optional but recommended: virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

`requirements.txt`:

```
pypdf>=6.0
reportlab>=4.0
pdfplumber>=0.11
```

| Library | Used for | Needed by |
|---|---|---|
| `pdfplumber` | Reading rectangles and word positions from the template | `extract_template_schema.py` (run once) |
| `reportlab` | Drawing wrapped, auto-sized text on the overlay page | `fill_tsow.py` |
| `pypdf` | Merging the overlay onto the template and saving | `fill_tsow.py` |

`json` and `sys` are part of Python's standard library.

## 3. Usage

### Step 1: generate the schema (only once per template)

```bash
python extract_template_schema.py TSOW_Template.pdf tsow_schema.json
```

`tsow_schema.json` already ships with the project. Re-run this only if the template changes.

### Step 2: fill the template

```bash
python fill_tsow.py TSOW_Template.pdf tsow_schema.json data.json output.pdf
```

Optional flag: `--no-highlight` turns off the yellow highlight on fields marked `needs_review`.

### Step 3: read the report

The script prints a JSON report:

| Key | Meaning |
|---|---|
| `filled` | Fields written, with the font size used |
| `missing_in_pdf` | JSON keys that match no template field (check spelling) |
| `empty` | Keys present but with blank values |
| `overflow` | Fields whose text did not fit even at the minimum font size (text is clipped) |
| `needs_review` | Fields highlighted yellow because the extractor flagged them |
| `not_provided` | Template fields that got no value |

## 4. Accepted JSON formats

### A) Extraction-pipeline format

```json
{
  "company_name": "Samsung",
  "questionnaire_answers": [
    {
      "standard_field": "Company Name",
      "answer": "Samsung",
      "confidence": 1.0,
      "needs_review": false
    }
  ]
}
```

Only `standard_field`, `answer` and `needs_review` are used. Empty answers are skipped.

### B) Flat format

```json
{
  "Company Name": "Acme Vision Inc.",
  "Performance Metrics": ["Throughput >= 60 FPS", "P95 latency < 50 ms"]
}
```

A list value becomes bullet points. Nested groups such as `{"Key Contacts": {"Intel": "..."}}` also work.

### Template fields (exact key names, case-insensitive)

`Company Name`, `Product Name`, `BU`, `Intel`, `ISV`, `CRM`, `Value Proposition`, `Use Case`, `AI Workload`, `Intel Software Stack`, `Model/s`, `Model Optimizations`, `OS`, `Intel Target Hardware`, `Performance Metrics`, `Success Criteria`, `Dependencies`

`Key Contacts` and `Targeted AI Approach` are section titles with no value cell and are ignored.

## 5. How it works

### extract_template_schema.py
1. Opens the PDF with **pdfplumber**.
2. Keeps rectangles that are cell-sized (wider than 20pt, taller than 10pt, narrower than the page, not the border color).
3. Reads the words inside each rectangle to get its label.
4. Looks for an empty neighbouring cell: to the **right** (same top and bottom), otherwise **below** (same left and right). A 1.5pt tolerance absorbs floating-point differences.
5. Labels with no empty neighbour are section headers and are skipped.
6. Saves `field -> {page, placement, bbox}` to `tsow_schema.json`. Coordinates are in points, origin top-left.

### fill_tsow.py
1. Normalizes the input JSON (formats A and B above).
2. Matches each key to a schema field, ignoring case.
3. Converts the value to text (lists become bullets, special characters are escaped).
4. Fits the text: tries 10pt and shrinks by 0.5pt down to 5pt until it fits the cell.
5. Draws it on an overlay, converting coordinates to the PDF origin (bottom-left) and clipping to the cell.
6. Optionally paints a translucent yellow background behind `needs_review` fields.
7. Merges the overlay onto the template with pypdf and writes the output PDF.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `DeprecationError: replace_contents ... pypdf 7.0.0` | Use the updated `fill_tsow.py` (it uses `PdfWriter(clone_from=...)`). |
| Key appears in `missing_in_pdf` | The key does not match a field name. Check spelling, for example `Model/s`. |
| Text is tiny or clipped | The value is too long for the cell. Shorten it, or check `overflow` in the report. |
| Strange characters in output | The built-in Helvetica font covers Latin text only. Register a TTF font with ReportLab for other scripts. |
| Template changed | Re-run `extract_template_schema.py`. |

## 7. Limitations

- Cells have a fixed size, so very long text shrinks or gets clipped.
- The schema extractor needs a template drawn with real rectangles. Scanned or image-only templates need OCR or manually entered coordinates.
- Values are top-aligned in their cells.
- The template here has one page. Multi-page templates are supported by the schema format but untested.
