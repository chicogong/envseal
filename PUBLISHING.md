# Publishing to PyPI

## Prerequisites

1. **PyPI Account**: Register at https://pypi.org/account/register/
2. **API Token**: Create at https://pypi.org/manage/account/token/
3. **Install tools**: `pipx install build twine`

## Build Process

### 1. Update Version

Edit `pyproject.toml`:
```toml
version = "0.1.0"  # Update as needed
```

### 2. Clean and Build

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build packages
pipx run build
```

This creates:
- `dist/envseal-X.Y.Z-py3-none-any.whl` (wheel)
- `dist/envseal-X.Y.Z.tar.gz` (source distribution)

### 3. Validate Packages

```bash
pipx run twine check dist/*
```

Should show:
```
Checking dist/envseal-0.1.0-py3-none-any.whl: PASSED
Checking dist/envseal-0.1.0.tar.gz: PASSED
```

## Publishing

### Test on TestPyPI (Recommended First)

1. **Register on TestPyPI**: https://test.pypi.org/account/register/

2. **Upload to TestPyPI**:
   ```bash
   pipx run twine upload --repository testpypi dist/*
   ```

3. **Test Installation**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ envseal
   ```

### Publish to PyPI

1. **Upload**:
   ```bash
   pipx run twine upload dist/*
   ```

2. **Enter credentials**:
   - Username: `__token__`
   - Password: Your PyPI API token (starts with `pypi-`)

3. **Verify**:
   Visit https://pypi.org/project/envseal/

### After Publishing

1. **Test Installation**:
   ```bash
   pipx install envseal
   envseal --version
   ```

2. **Create Git Tag**:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. **Create GitHub Release**:
   - Go to https://github.com/chicogong/envseal/releases
   - Click "Draft a new release"
   - Select the tag
   - Add release notes

## Updating the Package

### For Bug Fixes (Patch Version)

```bash
# Update version: 0.1.0 → 0.1.1
# Edit pyproject.toml
rm -rf dist/
pipx run build
pipx run twine upload dist/*
```

### For New Features (Minor Version)

```bash
# Update version: 0.1.1 → 0.2.0
# Edit pyproject.toml
rm -rf dist/
pipx run build
pipx run twine upload dist/*
```

### For Breaking Changes (Major Version)

```bash
# Update version: 0.2.0 → 1.0.0
# Edit pyproject.toml
rm -rf dist/
pipx run build
pipx run twine upload dist/*
```

## Configuration File (~/.pypirc)

Optional, to avoid entering credentials each time:

```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

**⚠️ Important**: Never commit `.pypirc` to Git!

## Checklist Before Publishing

- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG updated (if you have one)
- [ ] README accurate
- [ ] Built packages validated (`twine check dist/*`)
- [ ] Tested on TestPyPI first
- [ ] Git committed and tagged

## Troubleshooting

### "File already exists" error
You've already uploaded this version. Increment the version number.

### "Invalid credentials" error
- Check that username is `__token__`
- Check that token starts with `pypi-`
- Regenerate token if needed

### Import errors after installation
Package name might conflict. Check on PyPI if name is already taken.

## Resources

- PyPI: https://pypi.org
- TestPyPI: https://test.pypi.org
- Twine docs: https://twine.readthedocs.io/
- Packaging guide: https://packaging.python.org/
