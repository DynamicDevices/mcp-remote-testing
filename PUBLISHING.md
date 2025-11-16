# Publishing Guide

This guide explains how to package and publish `ai-lab-testing` to PyPI.

## ⚠️ Alpha Quality Notice

**IMPORTANT**: This package is currently published as **alpha quality** software:
- **Not ready for professional or production use**
- API may change without notice
- Features may be incomplete or unstable
- Bugs are expected
- Use at your own risk

The package is published to PyPI for:
- Early testing and feedback
- Development and experimentation
- Community contribution

**Do not use in production environments or critical systems.**

## Prerequisites

### 1. PyPI Accounts

Create accounts on both platforms:
- **[Test PyPI](https://test.pypi.org/account/register/)** - For testing releases
- **[PyPI](https://pypi.org/account/register/)** - For production releases

**Note**: You can use the same email/password for both, but they are separate accounts.

### 2. API Tokens

Generate API tokens (recommended over passwords):

**Test PyPI:**
1. Go to https://test.pypi.org/manage/account/token/
2. Click "Add API token"
3. Name it (e.g., "ai-lab-testing-testpypi")
4. Scope: "Entire account" (or "Project: ai-lab-testing" if you prefer)
5. Copy the token (starts with `pypi-`)

**Production PyPI:**
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name it (e.g., "ai-lab-testing-pypi")
4. Scope: "Entire account" (or "Project: ai-lab-testing" if you prefer)
5. Copy the token (starts with `pypi-`)

**Security**: Store tokens securely. Never commit them to git.

### 3. Build Tools

Install required Python packages:
```bash
python3.10 -m pip install --upgrade build twine
```

### 4. Verify Package Name Availability

Before first publish, verify the package name is available:
- Check https://pypi.org/project/ai-lab-testing/ (should not exist or be yours)
- Check https://test.pypi.org/project/ai-lab-testing/ (should not exist or be yours)

## Configuration

### PyPI Credentials

Create `~/.pypirc` file:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-<your-production-token>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-<your-test-token>
```

**Security Note**: Never commit `.pypirc` to git. Add it to `.gitignore`.

## Building the Package

### 1. Clean Previous Builds

```bash
make clean
```

### 2. Build Distribution Files

```bash
make build
```

This creates:
- `dist/lab_testing-<version>-py3-none-any.whl` (wheel)
- `dist/lab_testing-<version>.tar.gz` (source distribution)

### 3. Check Distribution

```bash
make check-dist
```

This validates the package files.

## Publishing

### Test on Test PyPI First

```bash
make publish-test
```

Then test installation:
```bash
python3.10 -m pip install --index-url https://test.pypi.org/simple/ ai-lab-testing
```

### Publish to Production PyPI

Once tested, publish to production:

```bash
make publish
```

## Version Management

### Update Version

1. Update version in `lab_testing/version.py`:
   ```python
   __version__ = "0.1.1"
   ```

2. Update version in `pyproject.toml`:
   ```toml
   version = "0.1.1"
   ```

3. Update `CHANGELOG.md` with release notes

4. Commit and tag:
   ```bash
   git add lab_testing/version.py pyproject.toml CHANGELOG.md
   git commit -m "Release version 0.1.1"
   git tag -a v0.1.1 -m "Release version 0.1.1"
   git push origin main --tags
   ```

5. Build and publish:
   ```bash
   make clean build publish
   ```

## Installation for Users

After publishing, users can install:

```bash
# From PyPI
python3.10 -m pip install ai-lab-testing

# With dev dependencies
python3.10 -m pip install "ai-lab-testing[dev]"
```

## Troubleshooting

### "Package already exists" Error

- Check if version already exists on PyPI
- Increment version number

### Authentication Errors

- Verify `.pypirc` file exists and has correct tokens
- Check token permissions on PyPI

### Build Errors

- Ensure all dependencies are listed in `pyproject.toml`
- Check `MANIFEST.in` includes all necessary files
- Run `make clean` before rebuilding

## Automated Publishing (GitHub Actions)

The project includes automated publishing via GitHub Actions. See `.github/workflows/build.yml`.

### Setup for Automated Publishing

1. **Add PyPI API Token to GitHub Secrets:**
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Your PyPI API token (starts with `pypi-`)
   - Click "Add secret"

2. **How It Works:**
   - Publishing is triggered when you create a GitHub Release
   - The workflow builds the package and publishes to PyPI
   - Uses trusted publishing (no password needed if configured)

3. **Manual Publishing (Alternative):**

If you prefer manual publishing or need to publish to Test PyPI:

```bash
# Build the package
make build

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Or upload to production PyPI
twine upload dist/*
```

### Trusted Publishing (Recommended)

PyPI supports trusted publishing via GitHub Actions. This is more secure than API tokens:

1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add pending publisher"
3. Select "GitHub" as the provider
4. Enter:
   - Owner: `DynamicDevices`
   - Repository name: `ai-lab-testing`
   - Workflow filename: `.github/workflows/build.yml`
5. Click "Add"

This allows the GitHub Action to publish without storing tokens in secrets.

