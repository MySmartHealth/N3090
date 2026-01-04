#!/bin/bash
# Install FAISS-GPU via conda (optional, for heavy-duty vector search)

set -e

echo "🚀 Installing FAISS-GPU for GPU-accelerated vector search..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Installing Miniconda..."
    
    # Download and install Miniconda
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p $HOME/miniconda3
    
    # Initialize conda
    eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
    conda init bash
    
    echo "✅ Miniconda installed"
fi

# Activate conda
eval "$(conda shell.bash hook)"

# Create/update environment with FAISS-GPU
echo "Installing FAISS-GPU from conda-forge and pytorch channels..."
conda install -y -c pytorch -c conda-forge faiss-gpu

echo ""
echo "✅ FAISS-GPU installed successfully!"
echo ""
echo "📝 To use FAISS-GPU in your application:"
echo "   1. Set environment variable: USE_FAISS_GPU=true"
echo "   2. FAISS will automatically use GPU 0 for vector search"
echo "   3. Hybrid mode: pgvector for storage, FAISS-GPU for search"
echo ""
echo "🔧 Verify installation:"
echo "   python -c 'import faiss; print(f\"FAISS version: {faiss.__version__}\")'"
echo "   python -c 'import faiss; print(f\"GPU available: {hasattr(faiss, \\\"StandardGpuResources\\\")}\\")'"
echo ""
echo "⚠️  Note: FAISS-GPU is optional. pgvector already provides efficient"
echo "    GPU-accelerated vector search via HNSW indexing in PostgreSQL."
