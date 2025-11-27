# DeepSeek OCR Toolkit

A comprehensive toolkit to convert PDF documents and images into clean Markdown using the `deepseek-ocr` model via `ollama`.

This project provides three ways to use the tool:
1. **CLI**: A command-line script for batch processing.
2. **Web UI**: A user-friendly Streamlit interface.
3. **API**: A FastAPI backend for integration.

## Features

- **PDF & Image Support**: Converts PDF pages and single images (PNG, JPG, etc.) to Markdown.
- **Automatic Cleaning**: Removes detector tags (`<|ref|>`, `<|det|>`) from the output.
- **LaTeX Formatting**: Automatically converts `\(...\)` to `$ ... $` and `\[...\]` to `$$ ... $$`.
- **Local Processing**: Uses `ollama` to run the `deepseek-ocr` model locally.

## Prerequisites

1. **System Dependencies**:
   - `ollama` CLI installed and running.
   - `deepseek-ocr` model pulled (`ollama pull deepseek-ocr`).
   - `poppler-utils` (required for PDF processing).
     - Ubuntu/Debian: `sudo apt-get install poppler-utils`
     - MacOS: `brew install poppler`

2. **Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Command Line Interface (CLI)

The core script `converter.py` can be used directly.

```bash
# Convert a PDF
python converter.py input.pdf -o output.md

# Convert an Image
python converter.py input.png

# Options
python converter.py --help
# --dpi: Set DPI for PDF conversion (default: 200)
# --no-clean: Disable automatic tag cleaning and LaTeX formatting
```

### 2. Web UI (Streamlit)

Launch a web interface to upload files and preview results.

```bash
streamlit run app.py
```
Then open the URL displayed in the terminal (usually `http://localhost:8501`).

### 3. API (FastAPI)

Start the REST API server.

```bash
python api.py
# OR
uvicorn api:app --host 0.0.0.0 --port 8000
```

**API Endpoint:** `POST /convert`

Example using `curl`:
```bash
curl -X POST "http://localhost:8000/convert" \
  -F "file=@document.pdf" \
  -F "clean=true" \
  -o output.md
```

## Project Structure

- `converter.py`: Core logic for OCR and text cleaning.
- `app.py`: Streamlit frontend application.
- `api.py`: FastAPI backend application.
- `requirements.txt`: Python package requirements.
