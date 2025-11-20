# Browser-Based Google Sheets Setup Guide

## Step-by-Step Instructions

### Step 1: Sign In to Google Cloud Console
The browser is currently showing the Google sign-in page. Please:
1. Enter your Google account email
2. Click "Next"
3. Enter your password
4. Complete any 2FA if required

### Step 2: Create a Project (if needed)
After signing in, you'll see the Google Cloud Console. If you don't have a project yet:

1. Click on the **project dropdown** at the top (shows "Select a project")
2. Click **"New Project"**
3. Enter project name: `Foundries Devices Export`
4. Click **"Create"**
5. Wait for project creation (takes ~10 seconds)
6. Select the new project from the dropdown

### Step 3: Enable Google Sheets API
Once you have a project selected:

1. The browser should navigate to: `https://console.cloud.google.com/apis/library/sheets.googleapis.com`
2. Click the **"Enable"** button (blue button on the page)
3. Wait for API to enable (~5 seconds)

### Step 4: Create Service Account
After API is enabled:

1. Go to: **APIs & Services** → **Credentials** (in the left sidebar)
   OR navigate directly to: `https://console.cloud.google.com/apis/credentials`
2. Click **"Create Credentials"** button (top of page)
3. Select **"Service Account"**
4. Fill in:
   - **Service account name**: `foundries-export`
   - **Service account ID**: (auto-filled)
   - **Description**: `Service account for Foundries devices export to Google Sheets`
5. Click **"Create and Continue"**
6. Skip role assignment (click **"Continue"**)
7. Click **"Done"**

### Step 5: Create and Download Key
1. You'll see your service account in the list
2. Click on the service account name (`foundries-export`)
3. Go to the **"Keys"** tab
4. Click **"Add Key"** → **"Create new key"**
5. Select **"JSON"** format
6. Click **"Create"**
7. The JSON file will download automatically

### Step 6: Save Credentials
After the file downloads:

1. Find the downloaded file (usually in `~/Downloads/`)
2. Copy it to the project root:
   ```bash
   cp ~/Downloads/foundries-export-*.json /home/ajlennon/data_drive/esl/mcp-remote-testing/credentials.json
   ```

### Step 7: Run Export
```bash
cd /home/ajlennon/data_drive/esl/mcp-remote-testing
python3 export_to_google_sheets.py --factory sentai
```

## Quick Navigation URLs

- **Google Sheets API**: https://console.cloud.google.com/apis/library/sheets.googleapis.com
- **Credentials Page**: https://console.cloud.google.com/apis/credentials
- **Service Accounts**: https://console.cloud.google.com/iam-admin/serviceaccounts

## What the Browser Will Help With

The browser will help you:
1. Navigate to the correct pages
2. Click the right buttons
3. Fill in forms
4. Download the credentials file

Let me know when you've signed in and I'll continue guiding you through the browser!

