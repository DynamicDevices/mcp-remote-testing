#!/bin/bash
# Interactive script to help set up Google Sheets export

echo "=========================================="
echo "Google Sheets Export Setup Helper"
echo "=========================================="
echo ""

# Check if credentials already exist
if [ -f "credentials.json" ]; then
    echo "✅ Found credentials.json in project root"
    echo ""
    read -p "Do you want to use this file? (y/n): " use_existing
    if [ "$use_existing" = "y" ] || [ "$use_existing" = "Y" ]; then
        echo "✅ Using existing credentials.json"
        exit 0
    fi
fi

echo "To enable Google Sheets export, you need to:"
echo ""
echo "1. Create a Google Cloud project"
echo "2. Enable Google Sheets API"
echo "3. Create a service account"
echo "4. Download credentials JSON"
echo ""
echo "📖 Full instructions: See GOOGLE_SHEETS_SETUP.md"
echo ""
read -p "Press Enter to open Google Cloud Console..."
echo ""

# Try to open browser
if command -v xdg-open > /dev/null; then
    xdg-open "https://console.cloud.google.com/apis/library/sheets.googleapis.com" 2>/dev/null &
elif command -v open > /dev/null; then
    open "https://console.cloud.google.com/apis/library/sheets.googleapis.com" 2>/dev/null &
else
    echo "Please open: https://console.cloud.google.com/apis/library/sheets.googleapis.com"
fi

echo ""
echo "After you download the credentials JSON file:"
echo ""
read -p "Enter the path to your downloaded credentials JSON file: " creds_path

if [ -f "$creds_path" ]; then
    cp "$creds_path" "$(pwd)/credentials.json"
    echo "✅ Copied credentials to $(pwd)/credentials.json"
    echo ""
    echo "You can now run:"
    echo "  python3 export_to_google_sheets.py --factory sentai"
else
    echo "❌ File not found: $creds_path"
    echo ""
    echo "Please manually copy your credentials JSON to:"
    echo "  $(pwd)/credentials.json"
fi

