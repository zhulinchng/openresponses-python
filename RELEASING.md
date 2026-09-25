# Releasing to PyPI

The package is published from GitHub Actions using PyPI Trusted Publishing (OIDC); no API token is stored in this repository.

## One-time PyPI setup

1. Create the `openresponses-py` project on PyPI if it does not already exist.
2. Add a Trusted Publisher for this GitHub repository:
   - Owner: `zhulinchng`
   - Repository: `openresponses-python`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`
3. Create a GitHub environment named `pypi` and restrict it to the release workflow or protected release tags.

## Release

1. Update `project.version` in `pyproject.toml` and `__version__` in `src/openresponses/__init__.py` together; the release workflow rejects mismatches.
2. Update the changelog/release notes if applicable.
3. Run the local release checks:

   ```bash
   python -m pytest -q
   python -m mypy src/openresponses
   python -m ruff check src/openresponses tests examples scripts
   python -m ruff format --check src/openresponses tests examples scripts
   python scripts/generate_models.py --check
   python -m build --sdist --wheel --outdir dist/
   python -m twine check dist/*
   python -m mkdocs build --strict
   ```

4. Commit and push the release changes to `main`.
5. Create and publish a GitHub release using the matching `v<project.version>` tag.
6. The `Publish Python package` workflow builds, tests, validates, and publishes the sdist and wheel to PyPI.


## 0.1.2 provider validation

The 0.1.2 release includes live consumer validation against Ollama, llama.cpp, and LM Studio for synchronous and asynchronous JSON, SSE, and function-tool requests. Compatibility mode normalizes provider-specific missing function-tool `strict` flags, function-argument stream indexes, and response `output_text` aggregation. vLLM and SGLang startup remained blocked by shared remote GPU occupancy; no unrelated provider process was stopped.
The workflow also supports manual dispatch, but a published GitHub release is the normal release trigger.
