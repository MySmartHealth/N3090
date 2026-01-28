#!/usr/bin/env python3
"""
Ingest PDF documents into RAG vector database
"""
import os
import sys
import hashlib
import asyncio
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pypdf
import psycopg2
from sentence_transformers import SentenceTransformer

# Database connection
DB_URL = os.getenv("DATABASE_URL", "postgresql://medical_ai:medical_ai_secure@localhost:5432/medical_ai_prod")

# Parse DB URL
def parse_db_url(url):
    """Parse postgresql URL into connection params"""
    # postgresql://user:pass@host:port/db
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "")
    userpass, hostdb = url.split("@")
    user, password = userpass.split(":")
    hostport, db = hostdb.split("/")
    host, port = hostport.split(":") if ":" in hostport else (hostport, "5432")
    return {"user": user, "password": password, "host": host, "port": port, "dbname": db}

def extract_pdf_text(pdf_path: str, chunk_size: int = 500) -> list:
    """Extract text from PDF and split into chunks"""
    chunks = []
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            full_text = ""
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text += f"\n[Page {page_num + 1}]\n{text}"
            
            # Split into chunks
            words = full_text.split()
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_text = " ".join(chunk_words)
                if len(chunk_text.strip()) > 50:  # Skip tiny chunks
                    chunks.append(chunk_text)
    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")
    
    return chunks

def ingest_documents(data_dir: str):
    """Ingest all PDFs in data directory into vector database"""
    
    print("🔄 Loading embedding model (BGE-large-en-v1.5)...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5', device='cpu')
    print(f"✅ Model loaded (dim={model.get_sentence_embedding_dimension()})")
    
    # Connect to database
    db_params = parse_db_url(DB_URL)
    print(f"🔄 Connecting to database: {db_params['dbname']}@{db_params['host']}...")
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()
    
    # Find PDFs
    data_path = Path(data_dir)
    pdf_files = list(data_path.glob("**/*.pdf"))
    print(f"📄 Found {len(pdf_files)} PDF files")
    
    total_chunks = 0
    for pdf_path in pdf_files:
        print(f"\n📖 Processing: {pdf_path.name}")
        
        # Extract chunks
        chunks = extract_pdf_text(str(pdf_path))
        print(f"   Extracted {len(chunks)} chunks")
        
        if not chunks:
            continue
        
        # Generate embeddings
        print(f"   🧠 Generating embeddings...")
        embeddings = model.encode(chunks, show_progress_bar=True, convert_to_numpy=True)
        
        # Insert into database
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc_id = hashlib.sha256(f"{pdf_path.name}_{i}".encode()).hexdigest()[:16]
            title = f"{pdf_path.stem} - Chunk {i+1}"
            
            # Convert embedding to list for postgres
            embedding_list = embedding.tolist()
            
            try:
                cur.execute("""
                    INSERT INTO medical_documents 
                    (document_id, title, content, document_type, specialty, source_url, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                """, (
                    doc_id,
                    title,
                    chunk,
                    "training_document",
                    "medical",
                    str(pdf_path),
                    embedding_list
                ))
            except Exception as e:
                print(f"   ⚠️  Error inserting chunk {i}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        total_chunks += len(chunks)
        print(f"   ✅ Inserted {len(chunks)} chunks")
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM medical_documents")
    count = cur.fetchone()[0]
    print(f"\n🎉 RAG Database populated!")
    print(f"   Total documents: {count}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/home/dgs/N3090/services/inference-node/data/training"
    ingest_documents(data_dir)
