import streamlit as st
import tempfile
import os
import re
import base64
from pathlib import Path
from PIL import Image
import converter

st.set_page_config(page_title="DeepSeek OCR Converter", layout="wide")

st.title("DeepSeek OCR: PDF/Image to Markdown")

# Sidebar configuration
st.sidebar.header("Configuration")
dpi = st.sidebar.number_input("PDF DPI", min_value=72, max_value=600, value=200, step=10)
prompt = st.sidebar.text_area("Prompt", value="<|grounding|>Convert the document to markdown.", height=100)
do_clean = st.sidebar.checkbox("Clean Output", value=True, help="Remove detector tags and coordinates")

uploaded_file = st.file_uploader("Choose a PDF or Image file", type=['pdf', 'png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    st.info(f"File uploaded: {uploaded_file.name}")
    
    if st.button("Convert"):
        # Create a temporary directory to handle files
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save uploaded file
            input_path = os.path.join(tmpdir, uploaded_file.name)
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                if uploaded_file.name.lower().endswith('.pdf'):
                    status_text.text("Converting PDF to images...")
                    pages = converter.pdf_to_images(input_path, dpi=dpi)
                    total_pages = len(pages)
                    
                    for i, img in enumerate(pages, start=1):
                        status_text.text(f"Processing page {i}/{total_pages}...")
                        
                        # Save page image for processing
                        img_path = os.path.join(tmpdir, f"page_{i}.png")
                        img.save(img_path, format='PNG')
                        
                        # Run OCR
                        out = converter.run_deepseek_for_image(img_path, prompt)
                        
                        if do_clean:
                            out = converter.extract_and_embed_images(out, img_path)
                            out = converter.clean_text(out)
                            
                        results.append((i, out))
                        
                        progress_bar.progress(i / total_pages)
                else:
                    # Image processing
                    status_text.text("Processing image...")
                    out = converter.run_deepseek_for_image(input_path, prompt)
                    
                    if do_clean:
                        out = converter.extract_and_embed_images(out, input_path)
                        out = converter.clean_text(out)
                        
                    results.append((1, out))
                    progress_bar.progress(100)
                
                status_text.text("Processing complete!")
                
                # Combine results
                full_text = f"<!-- Generated from {uploaded_file.name} -->\n\n"
                for i, text in results:
                    if len(results) > 1:
                        full_text += f"<!-- Page {i} -->\n\n"
                    
                    full_text += text + "\n\n"
                
                # Display result
                st.subheader("Markdown Output")
                
                # Download button
                st.download_button(
                    label="Download Markdown",
                    data=full_text,
                    file_name=f"{Path(uploaded_file.name).stem}.md",
                    mime="text/markdown"
                )
                
                # Show raw text in an expander
                with st.expander("View Raw Markdown Source", expanded=True):
                    # Create a version with truncated base64 for display
                    display_text = re.sub(
                        r'!\[(.*?)\]\(data:image/.*?;base64,.*?\)',
                        r'![\1](data:image/...;base64,...omitted...)',
                        full_text,
                        flags=re.DOTALL
                    )
                    st.code(display_text, language="markdown")
                
                # Preview rendered markdown (might not be perfect for complex layouts)
                with st.expander("Preview Rendered Markdown"):
                    # Split text by base64 image pattern to render images separately
                    # This avoids freezing the browser with huge base64 strings in st.markdown
                    pattern = r'!\[.*?\]\(data:image/.*?;base64,(.*?)\)'
                    parts = re.split(pattern, full_text)
                    
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            if part.strip():
                                st.markdown(part)
                        else:
                            try:
                                image_data = base64.b64decode(part)
                                st.image(image_data)
                            except Exception:
                                st.warning("Could not render embedded image")

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
