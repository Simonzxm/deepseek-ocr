from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import PlainTextResponse
import shutil
import os
import tempfile
from pathlib import Path
import converter

app = FastAPI(title="DeepSeek OCR API")

@app.post("/convert", response_class=PlainTextResponse)
async def convert_document(
    file: UploadFile = File(...),
    dpi: int = Form(200),
    prompt: str = Form("<|grounding|>Convert the document to markdown."),
    clean: bool = Form(True)
):
    """
    Convert a PDF or Image file to Markdown.
    Returns the generated markdown text.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, file.filename)
        
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        results = []
        
        try:
            if file.filename.lower().endswith('.pdf'):
                # PDF processing
                try:
                    pages = converter.pdf_to_images(input_path, dpi=dpi)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"PDF conversion failed: {str(e)}")

                for i, img in enumerate(pages, start=1):
                    img_path = os.path.join(tmpdir, f"page_{i}.png")
                    img.save(img_path, format='PNG')
                    
                    try:
                        out = converter.run_deepseek_for_image(img_path, prompt)
                        if clean:
                            out = converter.extract_and_embed_images(out, img_path)
                            out = converter.clean_text(out)
                        results.append((i, out))
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"OCR failed on page {i}: {str(e)}")
            else:
                # Image processing
                try:
                    out = converter.run_deepseek_for_image(input_path, prompt)
                    if clean:
                        out = converter.extract_and_embed_images(out, input_path)
                        out = converter.clean_text(out)
                    results.append((1, out))
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"OCR failed on image: {str(e)}")

            # Combine results
            full_text = f"<!-- Generated from {file.filename} -->\n\n"
            for i, text in results:
                if len(results) > 1:
                    full_text += f"<!-- Page {i} -->\n\n"
                
                full_text += text + "\n\n"
            
            return full_text

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
