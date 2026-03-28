# Tesseract OCR on Windows (for image document ingestion)

Image uploads (JPG, PNG, …) can extract **searchable text** when both are installed:

1. **Python:** `pytesseract` (listed in `requirements.txt`)
2. **System:** [Tesseract](https://github.com/tesseract-ocr/tesseract) executable (`tesseract.exe`)

---

## 1. Install Tesseract (binary)

### Option A — winget (recommended)

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

Restart the terminal after install. The installer usually adds Tesseract to `PATH`.

### Option B — Chocolatey

```powershell
choco install tesseract
```

### Option C — Manual

1. Download the installer from [UB Mannheim Tesseract builds for Windows](https://github.com/UB-Mannheim/tesseract/wiki).
2. Install (note the folder, e.g. `C:\Program Files\Tesseract-OCR\`).
3. Either add `C:\Program Files\Tesseract-OCR` to your user **PATH**, or set `TESSERACT_CMD` in `.env` (see below).

Verify in **PowerShell**:

```powershell
tesseract --version
```

---

## 2. Python package

From the project root:

```powershell
pip install -r requirements.txt
```

(`pytesseract` is included.)

---

## 3. If `tesseract` is not on PATH

Create or edit `.env` in the project root:

```env
# Full path to tesseract.exe (use forward slashes or doubled backslashes)
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe

# Optional: OCR languages (Arabic + English for brochures). Requires matching tessdata packs.
# If Arabic packs are missing, use eng only or install ara from the Tesseract project.
TESSERACT_LANG=ara+eng
```

Restart `runserver` after changing `.env`.

---

## 4. Arabic (optional)

For better Arabic OCR, ensure `ara` trained data is installed (many Windows installers include multiple languages; otherwise add `tessdata` from the Tesseract project).

---

## 5. Verify from the project

```powershell
cd C:\Users\nageh\.cursor\projects\Realestate
.\.venv\Scripts\Activate.ps1
python manage.py check_ocr
```

You should see **Tesseract (binary): yes**, a version line, **TESSERACT_LANG**, and **Installed tessdata**. If you get a warning about missing `ara`, install Arabic trained data or set `TESSERACT_LANG=eng` until then.

The **Onboarding** page in the operator console also shows whether OCR is ready.

---

## 6. Re-parse documents after enabling OCR

`reindex_knowledge` only **re-embeds** existing chunk text. If images were ingested **before** Tesseract worked, you must **parse again** from the saved file:

```powershell
# Preview what would run
python manage.py reparse_documents --images-only --dry-run

# Re-parse all image-backed documents (jpg, png, …)
python manage.py reparse_documents --images-only

# Or specific IDs (from console Knowledge list)
python manage.py reparse_documents --document-ids 21,22,30
```

Requirements: the original upload must still exist at `RawDocument.file_path` (default onboarding uploads under `MEDIA_ROOT`). If the file was deleted, upload again.

---

## Troubleshooting

| Symptom | What to do |
|--------|------------|
| `TesseractNotFoundError` | Install Tesseract or set `TESSERACT_CMD` |
| `pytesseract` import error | `pip install pytesseract` |
| Empty OCR text | Image quality / language pack; try PDF with selectable text |

For the strongest answers in chat, prefer **PDF with real text**; use OCR on images when PDF is not available.
