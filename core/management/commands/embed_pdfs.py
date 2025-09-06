from django.core.management.base import BaseCommand, CommandError
import os
import faiss
import logging
import numpy as np
from typing import List, Dict, Tuple
from django.conf import settings
from core.utils import (
    extract_text_from_pdf, 
    chunk_text, 
    embed_texts, 
    normalize, 
    save_index, 
    save_metadata
)

# Configure logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Embed PDFs into FAISS index with enhanced error handling and progress tracking"

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf-dir',
            type=str,
            default=getattr(settings, 'PDF_DIRECTORY', 'pdfs'),
            help='Directory containing PDF files (default: pdfs)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rebuild even if index exists'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing chunks (default: 100)'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Reduce output verbosity (useful when called from auto-startup)'
        )

    def handle(self, *args, **options):
        pdf_dir = options['pdf_dir']
        force_rebuild = options['force']
        batch_size = options['batch_size']
        quiet = options['quiet']
        
        try:
            self.process_pdfs(pdf_dir, force_rebuild, batch_size, quiet)
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise CommandError(f"Failed to embed PDFs: {e}")

    def process_pdfs(self, pdf_dir: str, force_rebuild: bool, batch_size: int, quiet: bool = False):
        """Process all PDFs in the directory and create embeddings."""
        
        # Check if PDF directory exists
        if not os.path.exists(pdf_dir):
            raise CommandError(f"PDF directory not found: {pdf_dir}")
        
        # Get list of PDF files
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(f"No PDF files found in {pdf_dir}")
                )
            return
        
        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(f"Found {len(pdf_files)} PDF files to process")
            )
        
        # Check if index already exists
        index_path = getattr(settings, 'INDEX_PATH', 'indexes/faiss_index.bin')
        if os.path.exists(index_path) and not force_rebuild:
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"FAISS index already exists at {index_path}. "
                        "Use --force to rebuild."
                    )
                )
            return
        
        # Process PDFs with progress tracking
        if not quiet:
            self.stdout.write("📖 Starting PDF text extraction and chunking...")
        docs, metadata = self.extract_and_chunk_pdfs(pdf_dir, pdf_files, quiet)
        
        if not docs:
            raise CommandError("No text content extracted from PDFs")
        
        # Generate embeddings with progress
        if not quiet:
            self.stdout.write("🧠 Generating embeddings for text chunks...")
        vectors = self.generate_embeddings(docs, batch_size, quiet)
        
        # Build and save index
        if not quiet:
            self.stdout.write("💾 Building and saving FAISS index...")
        self.build_and_save_index(vectors, metadata, quiet)
        
        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(
                    f"🎉 Successfully processed {len(pdf_files)} PDFs, "
                    f"created {len(docs)} chunks, and saved FAISS index"
                )
            )

    def extract_and_chunk_pdfs(self, pdf_dir: str, pdf_files: List[str], quiet: bool = False) -> Tuple[List[str], List[Dict]]:
        """Extract text from PDFs and create chunks with progress tracking."""
        docs = []
        metadata = []
        
        if not quiet:
            self.stdout.write(f"📄 Processing {len(pdf_files)} PDF files...")
        
        for i, fname in enumerate(pdf_files, 1):
            if not quiet:
                self.stdout.write(f"📖 Processing {fname} ({i}/{len(pdf_files)})...")
            
            try:
                path = os.path.join(pdf_dir, fname)
                text = extract_text_from_pdf(path)
                
                if not text.strip():
                    if not quiet:
                        self.stdout.write(
                            self.style.WARNING(f"⚠️  No text extracted from {fname}")
                        )
                    continue
                
                chunks = chunk_text(text)
                
                if not chunks:
                    if not quiet:
                        self.stdout.write(
                            self.style.WARNING(f"⚠️  No chunks created from {fname}")
                        )
                    continue
                
                for chunk_idx, chunk in enumerate(chunks):
                    docs.append(chunk)
                    metadata.append({
                        "filename": fname,
                        "chunk_index": chunk_idx,
                        "text": chunk,
                        "char_count": len(chunk)
                    })
                
                if not quiet:
                    self.stdout.write(
                        f"✅ Extracted {len(chunks)} chunks from {fname}"
                    )
                
            except Exception as e:
                if not quiet:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error processing {fname}: {e}")
                    )
                logger.error(f"Error processing {fname}: {e}")
                continue
        
        if not quiet:
            self.stdout.write(f"📊 Total: {len(docs)} text chunks created from {len(pdf_files)} PDFs")
        return docs, metadata

    def generate_embeddings(self, docs: List[str], batch_size: int, quiet: bool = False) -> np.ndarray:
        """Generate embeddings for document chunks with progress tracking."""
        try:
            # Process in batches to manage memory
            all_vectors = []
            total_batches = (len(docs) + batch_size - 1) // batch_size
            
            if not quiet:
                self.stdout.write(f"🧠 Processing {len(docs)} chunks in {total_batches} batches...")
            
            for i in range(0, len(docs), batch_size):
                batch_num = i // batch_size + 1
                batch = docs[i:i + batch_size]
                
                if not quiet:
                    self.stdout.write(
                        f"🔄 Processing batch {batch_num}/{total_batches} "
                        f"({len(batch)} chunks)..."
                    )
                
                batch_vectors = embed_texts(batch)
                all_vectors.append(batch_vectors)
                
                if not quiet:
                    self.stdout.write(f"✅ Batch {batch_num} completed")
            
            # Combine all vectors
            if not quiet:
                self.stdout.write("🔗 Combining all embedding vectors...")
            vectors = np.vstack(all_vectors)
            vectors = normalize(vectors)
            
            if not quiet:
                self.stdout.write(
                    f"✅ Generated embeddings with shape: {vectors.shape}"
                )
            
            return vectors
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def build_and_save_index(self, vectors: np.ndarray, metadata: List[Dict], quiet: bool = False):
        """Build FAISS index and save both index and metadata."""
        try:
            if not quiet:
                self.stdout.write("🏗️  Building FAISS index...")
            
            # Create FAISS index
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            
            if not quiet:
                self.stdout.write(f"💾 Saving index and metadata...")
            
            # Save index and metadata
            save_index(index)
            save_metadata(metadata)
            
            if not quiet:
                self.stdout.write(
                    f"✅ FAISS index built with {index.ntotal} vectors"
                )
            
        except Exception as e:
            logger.error(f"Error building/saving index: {e}")
            raise
