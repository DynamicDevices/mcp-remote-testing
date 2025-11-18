#!/usr/bin/env python3
"""Test create_network_map MCP tool"""
import sys
import time
from lab_testing.server.tool_handlers import handle_tool
from mcp.types import TextContent, ImageContent

# Simulate MCP tool call
request_id = 'test_123'
start_time = time.time()
arguments = {
    'quick_mode': True,
    'scan_networks': False,
    'test_configured_devices': True
}

print('Calling create_network_map via MCP tool handler...')
print('='*70)

try:
    result = handle_tool('create_network_map', arguments, request_id, start_time)
    
    print(f'Returned {len(result)} content item(s):')
    print()
    
    for i, content in enumerate(result, 1):
        if isinstance(content, TextContent):
            print(f'Content {i}: TextContent')
            text = content.text
            if text.startswith('```mermaid'):
                print('  Type: Mermaid Diagram (PRIMARY)')
                print(f'  Length: {len(text)} characters')
                print('\n' + '='*70)
                print('FULL MERMAID DIAGRAM:')
                print('='*70)
                print(text)
                print('='*70)
            else:
                print('  Type: Text')
                print(f'  Length: {len(text)} characters')
                print(f'  Preview: {text[:200]}...')
        elif isinstance(content, ImageContent):
            print(f'Content {i}: ImageContent (FALLBACK)')
            print(f'  MIME Type: {content.mimeType}')
            print(f'  Data length: {len(content.data)} bytes (base64)')
            print(f'  Preview: {content.data[:100]}...')
        print()
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

