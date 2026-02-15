#!/bin/bash
# Launch script for BITA Dashboard

echo "🎯 BITA - Business-IT Alignment System"
echo "======================================="
echo ""

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "✓ Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY environment variable is not set."
    echo "You can set it now or enter it in the dashboard interface."
    echo ""
    read -p "Do you want to set it now? (y/n): " set_key

    if [ "$set_key" = "y" ] || [ "$set_key" = "Y" ]; then
        read -sp "Enter your OpenAI API key: " api_key
        export OPENAI_API_KEY="$api_key"
        echo ""
        echo "✅ API key set for this session"
    fi
fi

echo ""
echo "🚀 Launching BITA Dashboard..."
echo "📍 URL: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Launch Streamlit
streamlit run dashboard/app.py
