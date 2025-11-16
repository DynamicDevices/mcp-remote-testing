# Security

## Credential Management

**No secrets in repository**: Credentials are cached in `~/.cache/lab-testing/credentials.json` (user's home directory, not in repo).

### Authentication Preferences

1. **SSH Public Keys** (preferred)
   - Automatically checked and installed when possible
   - No passwords needed
   - Most secure method

2. **Passwordless Sudo** (preferred for debugging)
   - Enabled automatically when setting up devices
   - Reduces need for password prompts

3. **sshpass** (fallback)
   - Used only when SSH keys not available
   - Passwords cached in user's home directory (not in repo)
   - Requires `sshpass` package: `sudo apt install sshpass`

### Credential Cache

- Location: `~/.cache/lab-testing/credentials.json`
- Permissions: 600 (read/write owner only)
- Format: JSON with device_id:credential_type keys
- Never committed to repository

### Best Practices

- Install SSH keys on all target devices during setup
- Enable passwordless sudo for debugging convenience
- Use password caching only when keys unavailable
- Regularly rotate credentials if passwords used
- Review credential cache: `~/.cache/lab-testing/credentials.json`

