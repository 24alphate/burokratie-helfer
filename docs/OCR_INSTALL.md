# OCR engine install (Tesseract)

Stage 4A added Python deps `pytesseract` + `Pillow`, but those are just
wrappers. The actual OCR engine `tesseract-ocr` runs as an OS binary. If
it's not installed, OCR is reported as `ocr_unavailable` to the user
(no crash, no blocked upload — Level 1/2/3 PDFs continue to work).

## Linux / Ubuntu / Debian (CI + most servers)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

## macOS

```bash
brew install tesseract tesseract-lang
```

## Windows (development only)

1. Download installer: <https://github.com/UB-Mannheim/tesseract/wiki>
2. During install, check the boxes for German (`deu`) and English (`eng`) language packs
3. Add the install directory (typically `C:\Program Files\Tesseract-OCR`) to `PATH`
4. Verify: `tesseract --version` from a fresh terminal

## Verify install

```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
python -c "import pytesseract; print(pytesseract.get_languages())"
```

You should see at minimum `['deu', 'eng', 'osd']`.

## Vercel / serverless deployment

Tesseract is NOT available by default on Vercel's Python runtime.
Options for production:
1. Use a Docker-based deployment with the binary pre-installed
2. Defer Stage 4A's actual OCR to Stage 4E's cloud provider (Google
   Document AI EU)
3. Disable OCR in production initially — the graceful fallback will
   surface `ocr_unavailable` and the user is told to upload a digital PDF

For the MVP, Option 3 is acceptable: Stage 4A is diagnostic-only, and
even with `ocr_unavailable` we still give the user honest feedback
("OCR is not installed on this server yet — please upload a digital PDF
if you have one").
