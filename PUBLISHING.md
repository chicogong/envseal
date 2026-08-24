# Publishing to PyPI

## Release authentication

Production releases use PyPI Trusted Publishing through
`.github/workflows/publish.yml`. No PyPI API token is stored in GitHub or on a
maintainer machine.

Configure the `envseal-vault` project once in PyPI:

- Owner: `chicogong`
- Repository: `envseal`
- Workflow: `publish.yml`
- Environment: `pypi`

The GitHub workflow receives a short-lived OIDC identity only when a GitHub
Release is published.

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
- `dist/envseal_vault-X.Y.Z-py3-none-any.whl` (wheel)
- `dist/envseal_vault-X.Y.Z.tar.gz` (source distribution)

### 3. Validate Packages

```bash
pipx run twine check dist/*
```

Should show:
```
Checking dist/envseal_vault-0.1.0-py3-none-any.whl: PASSED
Checking dist/envseal_vault-0.1.0.tar.gz: PASSED
```

## Publishing

1. Merge the verified release commit into `master` and wait for CI.
2. Create and push the signed-off version tag, for example `v0.4.0`.
3. Publish a GitHub Release for that tag.
4. The `Publish to PyPI` workflow rebuilds, tests, validates, and uploads the
   package using OIDC.
5. Verify both PyPI metadata and a clean installation in an isolated venv.

### After Publishing

1. **Test Installation**:
   ```bash
   pipx install envseal-vault
   envseal --version
   ```

2. Confirm the GitHub Actions `Publish to PyPI` run succeeded.
3. Confirm the PyPI files were built from the same release tag.

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

## Emergency manual publishing

Manual token uploads are not the default. If Trusted Publishing is unavailable,
stop and diagnose the workflow rather than creating a broad account token. Any
emergency project-scoped token must be short-lived, entered outside shell argv,
and revoked immediately after verification.

## Checklist Before Publishing

- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG updated (if you have one)
- [ ] README accurate
- [ ] Built packages validated (`twine check dist/*`)
- [ ] PyPI Trusted Publisher matches owner/repository/workflow/environment
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
