#!/usr/bin/env python3
"""
Export Foundries devices data to Google Sheets.

Requirements:
1. Install: pip install gspread google-auth
2. Create a Google Cloud project and enable Google Sheets API
3. Create a service account and download credentials JSON
4. Share your Google Sheet with the service account email
5. Set GOOGLE_SHEETS_CREDENTIALS environment variable to path of credentials JSON
   OR place credentials.json in the project root

Usage:
    python export_to_google_sheets.py [--spreadsheet-id SPREADSHEET_ID] [--sheet-name SHEET_NAME]
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("ERROR: gspread and google-auth are required.")
    print("Install with: pip install gspread google-auth")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from lab_testing.tools.foundries_devices import list_foundries_devices


def get_google_credentials():
    """Get Google Sheets credentials from environment or file."""
    # Check environment variable first
    creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    
    # Fall back to credentials.json in project root
    if not creds_path:
        creds_path = Path(__file__).parent / "credentials.json"
        if not creds_path.exists():
            raise FileNotFoundError(
                "Google Sheets credentials not found. "
                "Set GOOGLE_SHEETS_CREDENTIALS environment variable or place credentials.json in project root."
            )
    
    creds_path = Path(creds_path)
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials file not found: {creds_path}")
    
    # Load credentials
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    
    creds = Credentials.from_service_account_file(str(creds_path), scopes=scope)
    return creds


def create_or_get_spreadsheet(gc, spreadsheet_id=None, title=None):
    """Create a new spreadsheet or get existing one."""
    if spreadsheet_id:
        try:
            return gc.open_by_key(spreadsheet_id)
        except Exception as e:
            print(f"ERROR: Could not open spreadsheet with ID {spreadsheet_id}: {e}")
            sys.exit(1)
    else:
        if not title:
            title = f"Foundries Devices Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return gc.create(title)


def export_devices_to_sheet(devices, worksheet, factory_name):
    """Export devices data to Google Sheet.
    
    SECURITY NOTE: This export only includes non-sensitive device metadata:
    - Device names, status, targets, apps
    - VPN IP addresses (not secrets)
    - Creation dates
    - Production flags
    
    NO SECRETS EXPORTED:
    - No API keys, tokens, or passwords
    - No private keys or certificates
    - No authentication credentials
    """
    if not devices:
        print("No devices to export")
        return
    
    # Define headers - ordered by importance/usefulness
    # SECURITY: Only include non-sensitive metadata
    headers = [
        "Name",
        "Status",
        "Target",
        "Apps",
        "Up-to-Date",
        "Is Production",
        "Created At",
        "Last Seen",
        "Updated At",
        "VPN IP",
        "Device Group",
        "Tag",
        "Owner",
        "OSTree Hash",
        "UUID",
        "Factory",
        "Days Since Created",  # Calculated field
        "Days Since Last Seen",  # Calculated field
    ]
    
    # Prepare data rows
    rows = [headers]
    
    # Calculate days since created for each device
    from datetime import datetime as dt
    
    def parse_date(date_str):
        """Parse date string from various formats."""
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                return dt.strptime(date_str.split("+")[0].split(".")[0].strip(), fmt)
            except ValueError:
                continue
        return None
    
    def days_since(date_str):
        """Calculate days since a date string."""
        date_obj = parse_date(date_str)
        if date_obj:
            return str((dt.now() - date_obj).days)
        return ""
    
    for device in devices:
        created_at = device.get("created_at", "")
        last_seen = device.get("last_seen", "")
        
        row = [
            device.get("name", ""),
            device.get("status", ""),
            device.get("target", ""),
            device.get("apps", ""),
            device.get("up_to_date", ""),
            device.get("is_prod", ""),
            created_at,
            last_seen,
            device.get("updated_at", ""),
            device.get("vpn_ip", ""),
            device.get("device_group", ""),
            device.get("tag", ""),
            device.get("owner", ""),
            device.get("ostree_hash", ""),
            device.get("uuid", ""),
            device.get("factory", factory_name),
            days_since(created_at),
            days_since(last_seen),
        ]
        rows.append(row)
    
    # Clear existing content and add new data
    worksheet.clear()
    worksheet.update(values=rows, range_name="A1")
    
    # Calculate column letter for last column
    def col_letter(col_num):
        """Convert column number (1-based) to letter (A, B, C, ..., Z, AA, AB, ...)"""
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(65 + (col_num % 26)) + result
            col_num //= 26
        return result
    
    last_col = col_letter(len(headers))
    header_range = f"A1:{last_col}1"
    
    # Format header row (bold, colored background)
    worksheet.format(header_range, {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
        "horizontalAlignment": "CENTER",
    })
    
    # Freeze header row for scrolling
    try:
        worksheet.freeze(rows=1)
    except Exception:
        pass  # Freeze might not be available in all gspread versions
    
    # Add filters to header row (makes spreadsheet filterable and sortable)
    # Filters automatically enable sorting on all columns
    try:
        spreadsheet = worksheet.spreadsheet
        # Use the correct API format for setBasicFilter
        requests = [{
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": len(devices) + 1,  # Include all data rows
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers),
                    }
                }
            }
        }]
        spreadsheet.batch_update({"requests": requests})
        print("✅ Filters added - columns are now sortable and filterable")
    except Exception as e:
        print(f"⚠️  Warning: Could not add filters automatically: {e}")
        print("   You can add filters manually: Select header row > Data > Create a filter")
        print("   This will enable sorting and filtering on all columns")
    
    # Auto-resize columns
    try:
        worksheet.columns_auto_resize(0, len(headers))
    except Exception:
        pass  # Auto-resize might not be available in all versions
    
    # Format specific columns for better readability
    if len(devices) > 0:
        # Status column - bold
        worksheet.format(f"B2:B{len(devices) + 1}", {
            "textFormat": {"bold": True},
        })
        
        # Up-to-Date column - bold
        worksheet.format(f"F2:F{len(devices) + 1}", {
            "textFormat": {"bold": True},
        })
    
    print(f"✅ Exported {len(devices)} devices to sheet '{worksheet.title}'")
    print(f"📊 Filters enabled on header row - click filter icons to filter/sort")


def main():
    parser = argparse.ArgumentParser(
        description="Export Foundries devices to Google Sheets"
    )
    parser.add_argument(
        "--spreadsheet-id",
        help="Google Spreadsheet ID (if not provided, creates a new spreadsheet)",
    )
    parser.add_argument(
        "--sheet-name",
        default="Devices",
        help="Name of the sheet/tab (default: 'Devices')",
    )
    parser.add_argument(
        "--factory",
        default="sentai",
        help="Factory name (default: 'sentai')",
    )
    parser.add_argument(
        "--title",
        help="Title for new spreadsheet (if creating new)",
    )
    
    args = parser.parse_args()
    
    # Get devices data
    print(f"Fetching devices from factory '{args.factory}'...")
    result = list_foundries_devices(factory=args.factory)
    
    if not result.get("success"):
        print(f"ERROR: Failed to fetch devices: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    devices = result.get("devices", [])
    print(f"✅ Retrieved {len(devices)} devices")
    
    if not devices:
        print("No devices to export")
        return
    
    # Authenticate with Google Sheets
    print("Authenticating with Google Sheets...")
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        print("✅ Authenticated successfully")
    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        print("\nTo set up Google Sheets API:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Sheets API")
        print("3. Create a service account and download credentials JSON")
        print("4. Share your spreadsheet with the service account email")
        print("5. Set GOOGLE_SHEETS_CREDENTIALS environment variable or place credentials.json in project root")
        sys.exit(1)
    
    # Create or get spreadsheet
    if args.spreadsheet_id:
        print(f"Opening spreadsheet with ID: {args.spreadsheet_id}")
        spreadsheet = create_or_get_spreadsheet(gc, spreadsheet_id=args.spreadsheet_id)
    else:
        title = args.title or f"Foundries Devices - {args.factory} - {datetime.now().strftime('%Y-%m-%d')}"
        print(f"Creating new spreadsheet: {title}")
        spreadsheet = create_or_get_spreadsheet(gc, title=title)
        print(f"✅ Created spreadsheet: {spreadsheet.url}")
    
    # Get or create worksheet
    try:
        worksheet = spreadsheet.worksheet(args.sheet_name)
        print(f"Using existing sheet: {args.sheet_name}")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=args.sheet_name, rows=1000, cols=20)
        print(f"Created new sheet: {args.sheet_name}")
    
    # Export data
    print(f"Exporting {len(devices)} devices to sheet...")
    export_devices_to_sheet(devices, worksheet, args.factory)
    
    print(f"\n✅ Export complete!")
    print(f"📊 Spreadsheet URL: {spreadsheet.url}")
    print(f"📋 Sheet name: {worksheet.title}")


if __name__ == "__main__":
    main()

