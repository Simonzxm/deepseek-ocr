#!/usr/bin/env python3
"""
Convert a PDF or Image to Markdown using the deepseek-ocr model via the `ollama` CLI.

Requirements:
- Python packages: pdf2image, Pillow (for PDF support)
- System: poppler (for pdf2image)
- ollama CLI with the `deepseek-ocr` model available locally

Example:
    python3 converter.py input.pdf -o output.md
    python3 converter.py input.png -o output.md

The script converts each PDF page to an image (or takes the input image), sends
it to `ollama run deepseek-ocr`, collects the responses and writes a single
markdown file.
"""

import argparse
import subprocess
import sys
import os
import tempfile
import re
import base64
import io
from pathlib import Path
from PIL import Image

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


def extract_and_embed_images(text: str, image_path: str) -> str:
    """
    Find <|ref|>image<|/ref|><|det|>[[x1,y1,x2,y2]]<|/det|> tags,
    crop the image from image_path, convert to base64, and embed as markdown image.
    """
    def replace_match(match):
        ref_type = match.group(1).strip()
        coords_str = match.group(2).strip()
        
        if ref_type != "image":
            return match.group(0)
            
        try:
            # Parse coordinates
            coords = [int(c.strip()) for c in coords_str.split(',')]
            if len(coords) != 4:
                return match.group(0)
                
            x1, y1, x2, y2 = coords
            
            # Crop and convert
            with Image.open(image_path) as img:
                width, height = img.size
                
                # DeepSeek-OCR coordinates are normalized to [0, 1000]
                # We need to scale them to the actual image dimensions
                x1 = int(x1 / 1000 * width)
                y1 = int(y1 / 1000 * height)
                x2 = int(x2 / 1000 * width)
                y2 = int(y2 / 1000 * height)
                
                cropped = img.crop((x1, y1, x2, y2))
                buffered = io.BytesIO()
                cropped.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
            return f"![image](data:image/png;base64,{img_b64})"
            
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to extract image: {e}\n")
            return match.group(0)

    pattern = r"<\|ref\|>(.*?)<\|/ref\|>\s*<\|det\|>\s*\[\[(.*?)\]\]\s*<\|/det\|>"
    return re.sub(pattern, replace_match, text, flags=re.DOTALL)


def clean_text(s: str) -> str:
    # Remove <|ref|>...</|ref|> blocks
    s = re.sub(r"<\|ref\|>.*?<\|/ref\|>", "", s, flags=re.DOTALL)

    # Remove <|det|>[[...]]<|/det|> blocks (coordinates)
    s = re.sub(r"<\|det\|>\s*\[\[.*?\]\]\s*<\|/det\|>", "", s, flags=re.DOTALL)

    # Remove any stray simple tags like <|ref|> or <|/ref|> just in case
    s = re.sub(r"<\|/?[A-Za-z0-9_+-]+\|>", "", s)

    # Replace LaTeX delimiters: \( .. \) -> $ .. $ and \[ .. \] -> $$ .. $$
    s = re.sub(r"\\\((.*?)\\\)", r"$\1$", s, flags=re.DOTALL)
    s = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", s, flags=re.DOTALL)

    # Collapse multiple blank lines into single blank line
    cleaned = re.sub(r"\n{2,}", "\n\n", s)

    return cleaned


def run_deepseek_for_image(image_path: str, prompt: str) -> str:
    input_arg = f"{image_path}\n{prompt}"
    cmd = ["ollama", "run", "deepseek-ocr", input_arg]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("`ollama` CLI not found. Install ollama and ensure it's on PATH.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ollama failed (exit {e.returncode}): {e.stderr}\nCommand: {' '.join(cmd)}")

    return proc.stdout.strip()


def pdf_to_images(pdf_path: str, dpi: int = 200):
    if convert_from_path is None:
        raise ImportError("pdf2image is not installed. Run: pip install pdf2image")
    return convert_from_path(pdf_path, dpi=dpi)


def main():
    parser = argparse.ArgumentParser(description="Convert PDF or Image to Markdown using deepseek-ocr (via ollama).")
    parser.add_argument("input", help="Input file path (PDF or Image)")
    parser.add_argument("-o", "--output", help="Output markdown file (default: input basename + .md)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI for PDF->image conversion (default: 200)")
    parser.add_argument("--prompt", default="<|grounding|>Convert the document to markdown.",
                        help="Prompt appended after the image path passed to deepseek-ocr")
    parser.add_argument("--no-clean", action="store_true", help="Disable cleaning of detector tags and coordinates (default: clean enabled)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(2)

    out_path = Path(args.output) if args.output else input_path.with_suffix('.md')
    results = []

    if input_path.suffix.lower() == '.pdf':
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"Converting PDF pages to images (dpi={args.dpi})...")
            try:
                pages = pdf_to_images(str(input_path), dpi=args.dpi)
            except Exception as e:
                print(f"Failed to convert PDF to images: {e}")
                print("Ensure poppler is installed and pdf2image is configured.")
                sys.exit(1)

            for i, img in enumerate(pages, start=1):
                img_path = os.path.join(tmpdir, f"page_{i}.png")
                img.save(img_path, format='PNG')
                print(f"Processing page {i}/{len(pages)} -> {img_path}")
                try:
                    out = run_deepseek_for_image(img_path, args.prompt)
                except Exception as e:
                    print(f"Error running deepseek-ocr on page {i}: {e}")
                    sys.exit(3)
                
                if not args.no_clean:
                    out = extract_and_embed_images(out, img_path)
                    out = clean_text(out)
                
                results.append((i, out))
    else:
        # Assume it is an image
        print(f"Processing image -> {input_path}")
        try:
            out = run_deepseek_for_image(str(input_path), args.prompt)
            
            if not args.no_clean:
                out = extract_and_embed_images(out, str(input_path))
                out = clean_text(out)
                
            results.append((1, out))
        except Exception as e:
            print(f"Error running deepseek-ocr on image: {e}")
            sys.exit(3)

    # Combine outputs into markdown
    print(f"Writing combined markdown to {out_path}")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"<!-- Generated by converter.py from {input_path.name} -->\n\n")
        for i, text in results:
            if len(results) > 1:
                f.write(f"<!-- Page {i} -->\n\n")
            f.write(text)
            f.write("\n\n")

    print("Done.")


if __name__ == '__main__':
    main()
