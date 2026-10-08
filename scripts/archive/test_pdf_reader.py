#!/usr/bin/env python3
# Test script to read PDF entry list

import PyPDF2
import re
from pathlib import Path

def read_pdf_text(pdf_path):
    """Read text content from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            
            print(f"PDF has {len(pdf_reader.pages)} pages")
            
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += f"\n--- PAGE {page_num + 1} ---\n"
                text += page_text
                print(f"Page {page_num + 1}: {len(page_text)} characters")
            
            return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

def extract_rider_info(text):
    """Extract rider information from PDF text"""
    riders = []
    
    # Look for patterns like "#19 JORDON SMITH" or "19 JORDON SMITH"
    # This regex looks for number followed by name
    pattern = r'#?(\d+)\s+([A-Z][A-Z\s]+?)(?=\s+[A-Z]{2,}|\s+\d+|\s*$)'
    
    matches = re.findall(pattern, text)
    
    for number, name in matches:
        # Clean up the name
        name = name.strip()
        if len(name) > 2:  # Filter out very short matches
            riders.append({
                'number': int(number),
                'name': name
            })
    
    return riders

def main():
    pdf_path = Path("Entry_List_250_west.pdf")
    
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return
    
    print(f"Reading PDF: {pdf_path}")
    text = read_pdf_text(pdf_path)
    
    if text:
        print("\n" + "="*50)
        print("FIRST 1000 CHARACTERS:")
        print("="*50)
        print(text[:1000])
        
        print("\n" + "="*50)
        print("EXTRACTING RIDER INFO:")
        print("="*50)
        
        riders = extract_rider_info(text)
        
        print(f"Found {len(riders)} potential riders:")
        for rider in riders[:20]:  # Show first 20
            print(f"  #{rider['number']} {rider['name']}")
        
        if len(riders) > 20:
            print(f"  ... and {len(riders) - 20} more")
    
    else:
        print("Failed to read PDF")

if __name__ == "__main__":
    main()

