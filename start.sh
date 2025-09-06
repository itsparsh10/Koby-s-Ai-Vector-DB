#!/bin/bash

echo "🚀 PDF Q&A System - Auto Startup"
echo "=================================="
echo

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: manage.py not found!"
    echo "Please run this script from the PDF project directory."
    exit 1
fi

# Check for PDF files in pdfs directory
echo "📚 Checking for PDF files in pdfs/ directory..."
PDF_COUNT=$(ls pdfs/*.pdf 2>/dev/null | wc -l)

if [ $PDF_COUNT -eq 0 ]; then
    echo "❌ No PDF files found in pdfs/ directory!"
    echo "Please add some PDF files to the pdfs/ folder and try again."
    exit 1
fi

echo "✅ Found $PDF_COUNT PDF files in pdfs/ directory:"
ls pdfs/*.pdf | sed 's/^/   - /'
echo

# Create indexes directory if it doesn't exist
if [ ! -d "indexes" ]; then
    echo "📁 Creating indexes directory..."
    mkdir -p indexes
fi

# Check if index already exists and needs updating
if [ -f "indexes/faiss_index.bin" ] && [ -f "indexes/metadata.json" ]; then
    echo "📋 Found existing index, checking if update is needed..."
    
    # Get the newest PDF modification time
    NEWEST_PDF=$(find pdfs -name "*.pdf" -printf '%T@\n' | sort -n | tail -1)
    NEWEST_PDF_TIME=${NEWEST_PDF%.*}
    
    # Get the newest index modification time
    NEWEST_INDEX=$(find indexes -name "*.bin" -o -name "*.json" -printf '%T@\n' | sort -n | tail -1)
    NEWEST_INDEX_TIME=${NEWEST_INDEX%.*}
    
    if [ "$NEWEST_PDF_TIME" -le "$NEWEST_INDEX_TIME" ]; then
        echo "✅ Index is up to date! No processing needed."
        INDEX_UPDATED=true
    else
        echo "🔄 PDFs have been modified, updating index..."
        INDEX_UPDATED=false
    fi
else
    echo "🔄 No existing index found, creating new index..."
    INDEX_UPDATED=false
fi

# Create/update the search index if needed
if [ "$INDEX_UPDATED" = false ]; then
    echo ""
    echo "🔍 Starting PDF processing and indexing..."
    echo "   This may take a few minutes depending on the number and size of PDFs."
    echo ""
    echo "🔄 Processing PDFs and generating embeddings..."
    echo "   Please wait, this process includes:"
    echo "   - Text extraction from PDFs"
    echo "   - Text chunking and processing"
    echo "   - Generating embeddings"
    echo "   - Building FAISS index"
    echo ""
    
    # Show progress indicator
    echo -n "⏳ Processing in progress"
    
    # Run the embedding command
    python manage.py embed_pdfs
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ PDF processing completed successfully!"
        
        # Show summary of what was processed
        if [ -f "indexes/metadata.json" ]; then
            echo "📊 Processing Summary:"
            
            # Count unique files
            UNIQUE_FILES=$(grep -o '"filename": "[^"]*"' indexes/metadata.json | sort -u | wc -l)
            echo "   - PDFs processed: $UNIQUE_FILES"
            
            # Count total chunks
            TOTAL_CHUNKS=$(grep -c '"chunk_index"' indexes/metadata.json)
            echo "   - Total text chunks: $TOTAL_CHUNKS"
            
            # Show index size
            if [ -f "indexes/faiss_index.bin" ]; then
                INDEX_SIZE=$(du -k indexes/faiss_index.bin | cut -f1)
                echo "   - Index size: ${INDEX_SIZE} KB"
            fi
        fi
    else
        echo ""
        echo "❌ Failed to create index. Please check the errors above."
        exit 1
    fi
fi

# Show completion message
echo ""
echo "🎉 PDF Processing Complete!"
echo "============================"
echo "✅ All PDFs have been processed and indexed"
echo "✅ Search index is ready"
echo "✅ System is ready to answer questions"
echo ""
echo "🚀 Starting web server..."
echo ""

# Start the Django server
echo "🌐 Django server starting..."
echo "   Server will be available at: http://localhost:8000"
echo "   Press Ctrl+C to stop the server"
echo "----------------------------------------"
echo ""

python manage.py runserver
