# Google Sheets Export Setup Guide

## Quick Setup Steps

### 1. Create Google Cloud Project and Enable API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Sheets API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

### 2. Create Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in:
   - **Service account name**: `foundries-devices-export` (or any name)
   - **Service account ID**: auto-generated
   - Click "Create and Continue"
4. Skip role assignment (click "Continue")
5. Click "Done"

### 3. Create and Download Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Select **JSON** format
5. Click "Create" - this downloads a JSON file

### 4. Save Credentials

**Option A: Place in project root**
```bash
# Copy the downloaded JSON file to project root as credentials.json
cp ~/Downloads/your-service-account-key.json /path/to/mcp-remote-testing/credentials.json
```

**Option B: Use environment variable**
```bash
export GOOGLE_SHEETS_CREDENTIALS=/path/to/your-service-account-key.json
```

### 5. Create or Share Google Sheet

**Option A: Create new spreadsheet (automatic)**
- The script will create a new spreadsheet automatically
- You'll get the URL in the output

**Option B: Use existing spreadsheet**
1. Create a Google Sheet manually
2. Share it with the **service account email** (found in the JSON file, looks like `xxx@xxx.iam.gserviceaccount.com`)
3. Give it "Editor" permissions
4. Copy the Spreadsheet ID from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
   - Use: `python3 export_to_google_sheets.py --spreadsheet-id SPREADSHEET_ID`

## Usage Examples

### Create new spreadsheet
```bash
python3 export_to_google_sheets.py --factory sentai
```

### Export to existing spreadsheet
```bash
python3 export_to_google_sheets.py --factory sentai --spreadsheet-id YOUR_SPREADSHEET_ID
```

### Custom sheet name
```bash
python3 export_to_google_sheets.py --factory sentai --sheet-name "Sentai Devices"
```

### Custom spreadsheet title
```bash
python3 export_to_google_sheets.py --factory sentai --title "My Foundries Devices"
```

## Troubleshooting

**Error: "Google Sheets credentials not found"**
- Make sure `credentials.json` is in the project root, OR
- Set `GOOGLE_SHEETS_CREDENTIALS` environment variable

**Error: "Permission denied" or "Spreadsheet not found"**
- Make sure you've shared the spreadsheet with the service account email
- Check that the service account email matches the one in your credentials JSON

**Error: "API not enabled"**
- Make sure Google Sheets API is enabled in your Google Cloud project

