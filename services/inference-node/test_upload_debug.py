#!/usr/bin/env python3
"""
Test script to debug PDF upload and extraction
"""
import requests
import sys

def test_upload(pdf_path):
    """Upload a PDF and show extraction results"""
    url = "http://localhost:8080/upload/claim-document"
    
    print(f"\n{'='*60}")
    print(f"Testing PDF Upload: {pdf_path}")
    print(f"{'='*60}\n")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path.split('/')[-1], f, 'application/pdf')}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', {})
            
            print("✓ Upload successful!")
            print(f"\nFile: {data.get('filename')}")
            print(f"Size: {data.get('file_size')} bytes")
            
            raw_text = data.get('raw_text', '')
            print(f"\n📄 Extracted Text ({len(raw_text)} chars):")
            print("-" * 60)
            print(raw_text[:1000])
            if len(raw_text) > 1000:
                print(f"\n... ({len(raw_text) - 1000} more characters)")
            print("-" * 60)
            
            fields = data.get('extracted_fields', {})
            print(f"\n📋 Extracted Fields ({len(fields)}):")
            if fields:
                for key, value in fields.items():
                    print(f"  • {key}: {value}")
            else:
                print("  ⚠ No fields extracted")
                print("\n  Possible reasons:")
                print("  1. PDF is image-based (needs OCR)")
                print("  2. Text doesn't match regex patterns")
                print("  3. Document format is unusual")
            
            print(f"\n💡 Debug Info:")
            print(f"  Raw text available: {'YES' if raw_text else 'NO'}")
            print(f"  Character count: {len(raw_text)}")
            print(f"  Contains 'patient': {'YES' if 'patient' in raw_text.lower() else 'NO'}")
            print(f"  Contains 'hospital': {'YES' if 'hospital' in raw_text.lower() else 'NO'}")
            print(f"  Contains 'diagnosis': {'YES' if 'diagnosis' in raw_text.lower() else 'NO'}")
            print(f"  Contains numbers: {'YES' if any(c.isdigit() for c in raw_text) else 'NO'}")
            
        else:
            print(f"✗ Upload failed: HTTP {response.status_code}")
            print(response.text)
    
    except FileNotFoundError:
        print(f"✗ File not found: {pdf_path}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_upload_debug.py <path_to_pdf>")
        print("\nExample:")
        print("  python test_upload_debug.py /tmp/sample_claim.pdf")
        sys.exit(1)
    
    test_upload(sys.argv[1])
