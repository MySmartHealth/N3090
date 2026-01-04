#!/usr/bin/env python3
"""
Example script for ingesting medical documents into the knowledge base.

This script demonstrates:
1. PDF ingestion with proper tagging
2. Web page ingestion from medical sources
3. Batch processing of multiple documents
4. Error handling and progress tracking
5. Post-ingestion verification

Usage:
    python examples/ingest_medical_documents.py --mode demo
    python examples/ingest_medical_documents.py --mode batch --directory /path/to/pdfs
    python examples/ingest_medical_documents.py --mode web --urls urls.txt
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.knowledge_base import DocumentIngestionEngine
from app.database import get_db


class MedicalDocumentIngestor:
    """Helper class for ingesting medical documents with progress tracking."""
    
    def __init__(self):
        self.engine = DocumentIngestionEngine()
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
    
    async def ingest_pdf(
        self,
        file_path: str,
        specialty: str,
        doc_type: str,
        title: Optional[str] = None,
        verified: bool = False
    ) -> Optional[str]:
        """
        Ingest a single PDF file.
        
        Args:
            file_path: Path to PDF file
            specialty: Medical specialty tag
            doc_type: Document type (guideline, research, etc.)
            title: Optional custom title
            verified: Whether document is medically verified
            
        Returns:
            Document ID if successful, None otherwise
        """
        self.stats["total"] += 1
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                self.stats["skipped"] += 1
                return None
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50 MB limit
                print(f"⚠️  Large file ({file_size / 1024 / 1024:.1f} MB), may take time: {file_path}")
            
            print(f"📄 Ingesting: {os.path.basename(file_path)}")
            
            # Ingest the PDF
            doc_id = await self.engine.ingest_pdf(
                file_path=file_path,
                specialty=specialty,
                doc_type=doc_type,
                title=title,
                verified=verified
            )
            
            print(f"   ✅ Success → Document ID: {doc_id}")
            self.stats["success"] += 1
            return doc_id
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
            self.stats["failed"] += 1
            return None
    
    async def ingest_directory(
        self,
        directory: str,
        specialty: str,
        doc_type: str,
        verified: bool = False,
        recursive: bool = True
    ) -> List[str]:
        """
        Batch ingest all PDFs from a directory.
        
        Args:
            directory: Directory path
            specialty: Medical specialty tag
            doc_type: Document type
            verified: Whether documents are verified
            recursive: Search subdirectories
            
        Returns:
            List of successfully ingested document IDs
        """
        print(f"\n📁 Scanning directory: {directory}")
        print(f"   Specialty: {specialty}")
        print(f"   Document Type: {doc_type}")
        print(f"   Verified: {verified}")
        print()
        
        # Find all PDF files
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(Path(directory).glob(pattern))
        
        if not pdf_files:
            print("⚠️  No PDF files found")
            return []
        
        print(f"Found {len(pdf_files)} PDF files\n")
        
        # Ingest each file
        document_ids = []
        for pdf_file in pdf_files:
            doc_id = await self.ingest_pdf(
                file_path=str(pdf_file),
                specialty=specialty,
                doc_type=doc_type,
                verified=verified
            )
            if doc_id:
                document_ids.append(doc_id)
            
            # Small delay to avoid overwhelming the database
            await asyncio.sleep(0.5)
        
        return document_ids
    
    async def ingest_web_page(
        self,
        url: str,
        specialty: str,
        doc_type: str,
        title: Optional[str] = None,
        verified: bool = False
    ) -> Optional[str]:
        """
        Ingest content from a web page.
        
        Args:
            url: Web page URL
            specialty: Medical specialty
            doc_type: Document type
            title: Optional custom title
            verified: Whether content is verified
            
        Returns:
            Document ID if successful
        """
        self.stats["total"] += 1
        
        try:
            print(f"🌐 Ingesting web page: {url}")
            
            doc_id = await self.engine.ingest_web_page(
                url=url,
                specialty=specialty,
                doc_type=doc_type,
                title=title,
                verified=verified
            )
            
            print(f"   ✅ Success → Document ID: {doc_id}")
            self.stats["success"] += 1
            return doc_id
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
            self.stats["failed"] += 1
            return None
    
    def print_stats(self):
        """Print ingestion statistics."""
        print("\n" + "="*50)
        print("📊 Ingestion Statistics")
        print("="*50)
        print(f"Total Attempted: {self.stats['total']}")
        print(f"✅ Successful:   {self.stats['success']}")
        print(f"❌ Failed:       {self.stats['failed']}")
        print(f"⏭️  Skipped:      {self.stats['skipped']}")
        print("="*50 + "\n")


async def demo_ingestion():
    """
    Demo mode: Ingest sample documentation files.
    
    This demonstrates the ingestion process using the existing docs/ directory.
    """
    print("🎯 Demo Mode: Ingesting sample documentation\n")
    
    ingestor = MedicalDocumentIngestor()
    
    # Sample documents from docs/ directory
    sample_docs = [
        {
            "path": "docs/KNOWLEDGE_BASE.md",
            "specialty": "ai_operations",
            "doc_type": "reference",
            "title": "Knowledge Base System Documentation",
            "verified": True
        },
        {
            "path": "docs/VLLM_SETUP.md",
            "specialty": "ai_operations",
            "doc_type": "reference",
            "title": "vLLM Setup Guide",
            "verified": True
        },
        {
            "path": "docs/TRAINING.md",
            "specialty": "ai_operations",
            "doc_type": "training",
            "title": "Model Training Documentation",
            "verified": True
        },
    ]
    
    # Ingest each document
    for doc in sample_docs:
        if os.path.exists(doc["path"]):
            # Use ingest_text_file for markdown files
            try:
                print(f"📝 Ingesting: {doc['title']}")
                doc_id = await ingestor.engine.ingest_text_file(
                    file_path=doc["path"],
                    specialty=doc["specialty"],
                    doc_type=doc["doc_type"],
                    title=doc["title"],
                    verified=doc["verified"]
                )
                print(f"   ✅ Success → Document ID: {doc_id}\n")
                ingestor.stats["success"] += 1
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}\n")
                ingestor.stats["failed"] += 1
            
            ingestor.stats["total"] += 1
        else:
            print(f"⚠️  File not found: {doc['path']}\n")
            ingestor.stats["skipped"] += 1
    
    ingestor.print_stats()
    
    # Show how to search the ingested content
    print("💡 To search the ingested content:")
    print("   python scripts/manage_knowledge_base.py search 'knowledge base'")
    print("   python scripts/manage_knowledge_base.py stats\n")


async def batch_ingestion(directory: str, specialty: str, doc_type: str, verified: bool = False):
    """
    Batch ingestion mode: Process all PDFs in a directory.
    
    Args:
        directory: Directory containing PDFs
        specialty: Medical specialty tag
        doc_type: Document type
        verified: Whether documents are verified
    """
    print(f"📚 Batch Ingestion Mode\n")
    
    ingestor = MedicalDocumentIngestor()
    
    document_ids = await ingestor.ingest_directory(
        directory=directory,
        specialty=specialty,
        doc_type=doc_type,
        verified=verified,
        recursive=True
    )
    
    ingestor.print_stats()
    
    if document_ids:
        print(f"✅ Successfully ingested {len(document_ids)} documents")
        print(f"   Document IDs: {', '.join(document_ids[:5])}{'...' if len(document_ids) > 5 else ''}\n")


async def web_ingestion(urls_file: str, specialty: str, doc_type: str, verified: bool = False):
    """
    Web ingestion mode: Process URLs from a file.
    
    Args:
        urls_file: Text file with one URL per line
        specialty: Medical specialty
        doc_type: Document type
        verified: Whether content is verified
    """
    print(f"🌐 Web Ingestion Mode\n")
    
    ingestor = MedicalDocumentIngestor()
    
    # Read URLs from file
    try:
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"❌ File not found: {urls_file}")
        return
    
    print(f"Found {len(urls)} URLs to process\n")
    
    # Ingest each URL
    for url in urls:
        await ingestor.ingest_web_page(
            url=url,
            specialty=specialty,
            doc_type=doc_type,
            verified=verified
        )
        await asyncio.sleep(1)  # Be polite to web servers
    
    ingestor.print_stats()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Ingest medical documents into the knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Demo mode (ingest sample docs)
  python examples/ingest_medical_documents.py --mode demo
  
  # Batch ingest PDFs from directory
  python examples/ingest_medical_documents.py \\
    --mode batch \\
    --directory data/clinical_guidelines \\
    --specialty cardiology \\
    --type guideline \\
    --verified
  
  # Ingest from URLs file
  python examples/ingest_medical_documents.py \\
    --mode web \\
    --urls-file medical_urls.txt \\
    --specialty oncology \\
    --type research
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['demo', 'batch', 'web'],
        default='demo',
        help='Ingestion mode (default: demo)'
    )
    
    parser.add_argument(
        '--directory',
        help='Directory containing PDFs (for batch mode)'
    )
    
    parser.add_argument(
        '--urls-file',
        help='File containing URLs to ingest (for web mode)'
    )
    
    parser.add_argument(
        '--specialty',
        default='general_medicine',
        help='Medical specialty tag (default: general_medicine)'
    )
    
    parser.add_argument(
        '--type',
        dest='doc_type',
        default='reference',
        choices=['guideline', 'protocol', 'research', 'reference', 'policy', 'training'],
        help='Document type (default: reference)'
    )
    
    parser.add_argument(
        '--verified',
        action='store_true',
        help='Mark documents as medically verified'
    )
    
    args = parser.parse_args()
    
    # Validate arguments based on mode
    if args.mode == 'batch' and not args.directory:
        parser.error("--directory is required for batch mode")
    
    if args.mode == 'web' and not args.urls_file:
        parser.error("--urls-file is required for web mode")
    
    # Run the appropriate ingestion mode
    if args.mode == 'demo':
        asyncio.run(demo_ingestion())
    elif args.mode == 'batch':
        asyncio.run(batch_ingestion(
            directory=args.directory,
            specialty=args.specialty,
            doc_type=args.doc_type,
            verified=args.verified
        ))
    elif args.mode == 'web':
        asyncio.run(web_ingestion(
            urls_file=args.urls_file,
            specialty=args.specialty,
            doc_type=args.doc_type,
            verified=args.verified
        ))


if __name__ == "__main__":
    main()
