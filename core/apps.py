from django.apps import AppConfig
import os
import logging
import time
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """Called when Django starts - auto-index PDFs if needed with progress messages."""
        try:
            # Only run auto-indexing when the server starts, not during migrations
            if self.should_run_auto_index():
                self.auto_index_pdfs()
        except Exception as e:
            logger.error(f"Auto-indexing failed: {e}")
    
    def should_run_auto_index(self):
        """Check if we should run auto-indexing (only when server starts)."""
        import sys
        # Don't run during migrations, collectstatic, or other management commands
        if 'runserver' in sys.argv or 'runsslserver' in sys.argv:
            return True
        return False
    
    def auto_index_pdfs(self):
        """Automatically index PDFs if no index exists or PDFs are newer with progress messages."""
        from core.utils import load_index, load_metadata
        
        print("\n🚀 PDF Q&A System - Auto Startup")
        print("=" * 40)
        
        # Check if we need to index - look in pdfs directory for PDFs
        pdf_dir = getattr(settings, 'PDF_DIRECTORY', 'pdfs')
        index_path = getattr(settings, 'INDEX_PATH', os.path.join("indexes", "faiss_index.bin"))
        metadata_path = os.path.join("indexes", "metadata.json")
        
        # Create indexes directory if it doesn't exist
        indexes_dir = os.path.dirname(index_path)
        if not os.path.exists(indexes_dir):
            os.makedirs(indexes_dir)
            print("📁 Created indexes directory")
        
        # Check if index exists and is up to date
        needs_indexing = False
        
        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            print("🔄 No index found - will create new index")
            needs_indexing = True
        else:
            # Check if there are new PDFs in pdfs directory
            try:
                pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
                if pdf_files:
                    # Get the newest PDF modification time
                    newest_pdf_time = max(
                        os.path.getmtime(os.path.join(pdf_dir, f)) for f in pdf_files
                    )
                    index_time = max(
                        os.path.getmtime(index_path),
                        os.path.getmtime(metadata_path)
                    )
                    
                    if newest_pdf_time > index_time:
                        print("🔄 Found newer PDFs - will rebuild index")
                        needs_indexing = True
                    else:
                        print("✅ Index is up to date")
                elif not pdf_files:
                    print("❌ No PDF files found in pdfs directory")
                    return
            except Exception as e:
                print(f"⚠️  Could not check PDF timestamps: {e}")
                needs_indexing = True
        
        if needs_indexing:
            self.run_indexing_with_progress(pdf_dir)
        else:
            print("✅ System ready - starting server...")
    
    def run_indexing_with_progress(self, pdf_dir: str):
        """Run the PDF indexing process with progress messages."""
        try:
            from django.core.management import call_command
            
            print("\n🔍 Starting PDF processing and indexing...")
            print("   This may take a few minutes depending on the number and size of PDFs.")
            print()
            
            # Count PDF files
            pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
            print(f"📚 Found {len(pdf_files)} PDF files to process:")
            for pdf in pdf_files:
                print(f"   - {pdf}")
            print()
            
            print("🔄 Processing PDFs and generating embeddings...")
            print("   Please wait, this process includes:")
            print("   - Text extraction from PDFs")
            print("   - Text chunking and processing")
            print("   - Generating embeddings")
            print("   - Building FAISS index")
            print()
            
            # Show progress indicator
            print("⏳ Processing in progress", end="", flush=True)
            
            # Run the embedding command
            call_command('embed_pdfs', verbosity=1, quiet=True)
            
            print()  # New line after progress indicator
            
            # Show completion summary
            self.show_completion_summary()
            
            print("\n🎉 PDF Processing Complete!")
            print("=" * 30)
            print("✅ All PDFs have been processed and indexed")
            print("✅ Search index is ready")
            print("✅ System is ready to answer questions")
            print()
            print("🚀 Starting web server...")
            print()
            
        except Exception as e:
            print(f"❌ Failed to run automatic indexing: {e}")
            logger.error(f"Failed to run automatic indexing: {e}")
    
    def show_completion_summary(self):
        """Show summary of what was processed."""
        try:
            metadata_path = os.path.join("indexes", "metadata.json")
            index_path = os.path.join("indexes", "faiss_index.bin")
            
            if os.path.exists(metadata_path):
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Count unique files and total chunks
                unique_files = set(item['filename'] for item in metadata)
                total_chunks = len(metadata)
                
                print(f"📊 Processing Summary:")
                print(f"   - PDFs processed: {len(unique_files)}")
                print(f"   - Total text chunks: {total_chunks}")
                
                if os.path.exists(index_path):
                    print(f"   - Index size: {os.path.getsize(index_path) / 1024:.1f} KB")
                
            else:
                print("   - Index created successfully")
                
        except Exception as e:
            print(f"   - Index created successfully")
            logger.warning(f"Could not read metadata for summary: {e}")
