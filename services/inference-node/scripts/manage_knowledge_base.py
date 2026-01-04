#!/usr/bin/env python3
"""
Knowledge Base Management CLI

Commands:
- ingest: Load documents into knowledge base
- search: Search knowledge base
- validate: Check knowledge quality
- gaps: Identify knowledge gaps from user feedback
- stats: Show knowledge base statistics
"""
import asyncio
import argparse
import sys
from pathlib import Path
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.knowledge_base import (
    get_ingestion_engine,
    get_attribution_engine,
    get_learning_engine
)
from app.database import AsyncSessionLocal, MedicalDocument
from sqlalchemy import select, func


async def ingest_pdf(args):
    """Ingest PDF document."""
    engine = get_ingestion_engine()
    
    doc_ids = await engine.ingest_pdf(
        pdf_path=args.file,
        title=args.title,
        specialty=args.specialty,
        document_type=args.type,
        source_url=args.url,
        metadata={"tags": args.tags.split(",") if args.tags else []}
    )
    
    logger.info(f"✅ Ingested {len(doc_ids)} chunks from PDF")
    for doc_id in doc_ids[:5]:  # Show first 5
        print(f"  - {doc_id}")
    if len(doc_ids) > 5:
        print(f"  ... and {len(doc_ids) - 5} more")


async def ingest_web(args):
    """Ingest web page."""
    engine = get_ingestion_engine()
    
    doc_id = await engine.ingest_web_page(
        url=args.url,
        title=args.title,
        specialty=args.specialty,
        document_type=args.type,
        quality_score=args.quality
    )
    
    if doc_id:
        logger.info(f"✅ Ingested web page: {doc_id}")
    else:
        logger.error("❌ Failed to ingest web page")


async def ingest_text(args):
    """Ingest text file."""
    engine = get_ingestion_engine()
    
    doc_id = await engine.ingest_text_file(
        file_path=args.file,
        title=args.title,
        specialty=args.specialty,
        document_type=args.type,
        source_url=args.url
    )
    
    if doc_id:
        logger.info(f"✅ Ingested text file: {doc_id}")
    else:
        logger.error("❌ Failed to ingest text file")


async def search_knowledge(args):
    """Search knowledge base."""
    from app.database import search_medical_documents
    
    results = await search_medical_documents(
        query=args.query,
        specialty=args.specialty,
        document_type=args.type,
        limit=args.limit
    )
    
    print(f"\n🔍 Found {len(results)} results for: {args.query}\n")
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} ({result['specialty']})")
        print(f"   Similarity: {result['similarity']:.2%}")
        print(f"   Type: {result['document_type']}")
        if result.get('source_url'):
            print(f"   Source: {result['source_url']}")
        print(f"   Content: {result['content'][:200]}...")
        print()


async def validate_knowledge(args):
    """Validate knowledge base quality."""
    engine = get_learning_engine()
    
    doc_ids = await engine.validate_knowledge(
        specialty=args.specialty,
        max_age_days=args.max_age
    )
    
    print(f"\n📋 Found {len(doc_ids)} documents needing validation\n")
    
    if args.list:
        async with AsyncSessionLocal() as session:
            from app.database import MedicalDocument
            
            for doc_id in doc_ids[:args.limit]:
                stmt = select(MedicalDocument).where(
                    MedicalDocument.document_id == doc_id
                )
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
                
                if doc:
                    print(f"- {doc.title}")
                    print(f"  ID: {doc.document_id}")
                    print(f"  Specialty: {doc.specialty}")
                    print(f"  Type: {doc.document_type}")
                    print(f"  Created: {doc.created_at}")
                    print(f"  Last Verified: {doc.last_verified or 'Never'}")
                    print()


async def find_knowledge_gaps(args):
    """Identify knowledge gaps from user feedback."""
    engine = get_learning_engine()
    
    gaps = await engine.identify_knowledge_gaps(
        days_back=args.days,
        min_occurrences=args.min_occurrences
    )
    
    print(f"\n🔍 Found {len(gaps)} knowledge gaps\n")
    
    for i, gap in enumerate(gaps, 1):
        print(f"{i}. Query: {gap['query'][:100]}...")
        print(f"   Occurrences: {gap['occurrences']}")
        print(f"   Avg Rating: {gap['avg_rating']:.1f}/5.0")
        print(f"   Gap Type: {gap['gap_type']}")
        print()


async def show_stats(args):
    """Show knowledge base statistics."""
    async with AsyncSessionLocal() as session:
        # Total documents
        stmt = select(func.count(MedicalDocument.id))
        result = await session.execute(stmt)
        total_docs = result.scalar()
        
        # By specialty
        stmt = select(
            MedicalDocument.specialty,
            func.count(MedicalDocument.id)
        ).group_by(
            MedicalDocument.specialty
        ).order_by(
            func.count(MedicalDocument.id).desc()
        )
        result = await session.execute(stmt)
        by_specialty = list(result)
        
        # By type
        stmt = select(
            MedicalDocument.document_type,
            func.count(MedicalDocument.id)
        ).group_by(
            MedicalDocument.document_type
        ).order_by(
            func.count(MedicalDocument.id).desc()
        )
        result = await session.execute(stmt)
        by_type = list(result)
        
        # Verification status
        stmt = select(
            MedicalDocument.verification_status,
            func.count(MedicalDocument.id)
        ).group_by(
            MedicalDocument.verification_status
        )
        result = await session.execute(stmt)
        by_status = list(result)
        
        # Quality score distribution
        stmt = select(
            func.avg(MedicalDocument.quality_score),
            func.min(MedicalDocument.quality_score),
            func.max(MedicalDocument.quality_score)
        )
        result = await session.execute(stmt)
        quality_stats = result.one()
    
    print("\n📊 Knowledge Base Statistics\n")
    print(f"Total Documents: {total_docs}")
    print()
    
    print("By Specialty:")
    for specialty, count in by_specialty:
        print(f"  - {specialty}: {count}")
    print()
    
    print("By Document Type:")
    for doc_type, count in by_type:
        print(f"  - {doc_type}: {count}")
    print()
    
    print("Verification Status:")
    for status, count in by_status:
        print(f"  - {status}: {count}")
    print()
    
    print("Quality Scores:")
    print(f"  - Average: {quality_stats[0]:.2f}")
    print(f"  - Min: {quality_stats[1]:.2f}")
    print(f"  - Max: {quality_stats[2]:.2f}")
    print()


async def batch_ingest_directory(args):
    """Batch ingest all files from a directory."""
    engine = get_ingestion_engine()
    directory = Path(args.directory)
    
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return
    
    pdf_files = list(directory.glob("**/*.pdf"))
    txt_files = list(directory.glob("**/*.txt"))
    
    total_files = len(pdf_files) + len(txt_files)
    print(f"\n📁 Found {total_files} files to ingest ({len(pdf_files)} PDFs, {len(txt_files)} text)\n")
    
    ingested = 0
    
    # Ingest PDFs
    for pdf_file in pdf_files:
        try:
            title = pdf_file.stem.replace("_", " ").replace("-", " ").title()
            doc_ids = await engine.ingest_pdf(
                pdf_path=str(pdf_file),
                title=title,
                specialty=args.specialty or "general",
                document_type=args.type or "reference"
            )
            ingested += len(doc_ids)
            print(f"✅ {pdf_file.name} → {len(doc_ids)} chunks")
        except Exception as e:
            print(f"❌ {pdf_file.name}: {e}")
    
    # Ingest text files
    for txt_file in txt_files:
        try:
            title = txt_file.stem.replace("_", " ").replace("-", " ").title()
            doc_id = await engine.ingest_text_file(
                file_path=str(txt_file),
                title=title,
                specialty=args.specialty or "general",
                document_type=args.type or "reference"
            )
            if doc_id:
                ingested += 1
                print(f"✅ {txt_file.name}")
        except Exception as e:
            print(f"❌ {txt_file.name}: {e}")
    
    print(f"\n✅ Batch ingestion complete: {ingested} documents")


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Base Management CLI"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Ingest PDF
    pdf_parser = subparsers.add_parser("ingest-pdf", help="Ingest PDF document")
    pdf_parser.add_argument("file", help="Path to PDF file")
    pdf_parser.add_argument("--title", required=True, help="Document title")
    pdf_parser.add_argument("--specialty", required=True, help="Medical specialty")
    pdf_parser.add_argument("--type", default="clinical_guideline", help="Document type")
    pdf_parser.add_argument("--url", help="Source URL")
    pdf_parser.add_argument("--tags", help="Comma-separated tags")
    
    # Ingest web
    web_parser = subparsers.add_parser("ingest-web", help="Ingest web page")
    web_parser.add_argument("url", help="Web page URL")
    web_parser.add_argument("--title", required=True, help="Document title")
    web_parser.add_argument("--specialty", required=True, help="Medical specialty")
    web_parser.add_argument("--type", default="web_resource", help="Document type")
    web_parser.add_argument("--quality", type=float, default=0.6, help="Quality score")
    
    # Ingest text
    text_parser = subparsers.add_parser("ingest-text", help="Ingest text file")
    text_parser.add_argument("file", help="Path to text file")
    text_parser.add_argument("--title", required=True, help="Document title")
    text_parser.add_argument("--specialty", required=True, help="Medical specialty")
    text_parser.add_argument("--type", default="reference", help="Document type")
    text_parser.add_argument("--url", help="Source URL")
    
    # Batch ingest
    batch_parser = subparsers.add_parser("batch-ingest", help="Batch ingest directory")
    batch_parser.add_argument("directory", help="Directory containing files")
    batch_parser.add_argument("--specialty", help="Default specialty")
    batch_parser.add_argument("--type", help="Default document type")
    
    # Search
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--specialty", help="Filter by specialty")
    search_parser.add_argument("--type", help="Filter by document type")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    
    # Validate
    validate_parser = subparsers.add_parser("validate", help="Validate knowledge")
    validate_parser.add_argument("--specialty", help="Filter by specialty")
    validate_parser.add_argument("--max-age", type=int, default=180, help="Max age in days")
    validate_parser.add_argument("--list", action="store_true", help="List documents")
    validate_parser.add_argument("--limit", type=int, default=20, help="Max to list")
    
    # Knowledge gaps
    gaps_parser = subparsers.add_parser("gaps", help="Find knowledge gaps")
    gaps_parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    gaps_parser.add_argument("--min-occurrences", type=int, default=3, help="Min occurrences")
    
    # Stats
    subparsers.add_parser("stats", help="Show statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == "ingest-pdf":
        asyncio.run(ingest_pdf(args))
    elif args.command == "ingest-web":
        asyncio.run(ingest_web(args))
    elif args.command == "ingest-text":
        asyncio.run(ingest_text(args))
    elif args.command == "batch-ingest":
        asyncio.run(batch_ingest_directory(args))
    elif args.command == "search":
        asyncio.run(search_knowledge(args))
    elif args.command == "validate":
        asyncio.run(validate_knowledge(args))
    elif args.command == "gaps":
        asyncio.run(find_knowledge_gaps(args))
    elif args.command == "stats":
        asyncio.run(show_stats(args))


if __name__ == "__main__":
    main()
