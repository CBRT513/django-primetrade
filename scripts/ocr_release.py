#!/usr/bin/env python3
"""
Simple OCR converter for scanned release PDFs.
Uses Google Cloud Vision API from BOL Redact project.
"""

import sys
from pathlib import Path
from google.cloud import vision
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfMerger
import tempfile
from PIL import Image

def resize_if_needed(image, max_pixels=50_000_000):
    """Resize image if it exceeds max pixels."""
    pixels = image.width * image.height
    if pixels > max_pixels:
        ratio = (max_pixels / pixels) ** 0.5
        new_size = (int(image.width * ratio), int(image.height * ratio))
        print(f"  Resizing from {image.size} to {new_size}")
        return image.resize(new_size, Image.Resampling.LANCZOS)
    return image

def ocr_scanned_pdf(input_pdf_path, output_pdf_path):
    """Convert scanned PDF to text-based PDF using OCR."""
    print(f"📄 Processing: {input_pdf_path}")
    
    # Initialize Vision API client
    client = vision.ImageAnnotatorClient()
    
    # Convert PDF pages to images (lower DPI to avoid huge images)
    print("🖼️  Converting PDF to images...")
    images = convert_from_path(input_pdf_path, dpi=150)  # Reduced from 300
    
    # Process each page
    temp_pdfs = []
    for i, image in enumerate(images, 1):
        print(f"📝 OCR'ing page {i}/{len(images)}...")
        
        # Resize if needed
        image = resize_if_needed(image)
        
        # Save image temporarily
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image.save(tmp.name, 'PNG')
            tmp_path = tmp.name
            
        # Run OCR
        with open(tmp_path, 'rb') as image_file:
            content = image_file.read()
        
        image_obj = vision.Image(content=content)
        response = client.text_detection(image=image_obj)
        
        if response.error.message:
            raise Exception(f"Vision API error: {response.error.message}")
        
        texts = response.text_annotations
        
        # Extract full text
        if texts:
            full_text = texts[0].description
        else:
            full_text = "[No text detected on this page]"
        
        # Create PDF page with OCR'd text
        temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_pdf.name, pagesize=letter)
        
        # Write text to PDF (simple layout)
        text_object = c.beginText(40, 750)
        text_object.setFont("Helvetica", 10)
        
        for line in full_text.split('\n'):
            if line.strip():  # Skip empty lines
                text_object.textLine(line.strip())
        
        c.drawText(text_object)
        c.save()
        
        temp_pdfs.append(temp_pdf.name)
        
        # Cleanup temp image
        Path(tmp_path).unlink()
    
    # Merge all pages
    print("📦 Merging pages...")
    merger = PdfMerger()
    for pdf_path in temp_pdfs:
        merger.append(pdf_path)
    
    merger.write(output_pdf_path)
    merger.close()
    
    # Cleanup temp PDFs
    for pdf_path in temp_pdfs:
        Path(pdf_path).unlink()
    
    print(f"✅ Complete: {output_pdf_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ocr_release.py input.pdf output.pdf")
        print("\nExample:")
        print('  python ocr_release.py "~/Downloads/INTAT 60045.pdf" ~/Downloads/INTAT_60045_ocr.pdf')
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    
    if not Path(input_pdf).exists():
        print(f"❌ Input file not found: {input_pdf}")
        sys.exit(1)
    
    ocr_scanned_pdf(input_pdf, output_pdf)
