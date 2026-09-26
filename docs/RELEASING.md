# Releasing Vega SDD

Maintainers publish a version only after source, docs and the wheel agree on the name, CLI and version. The initial public release uses `vega-sdd` as the distribution name and `sdd` as the command. The import module is `universal_sdd` for compatibility.

1. Update `pyproject.toml`, `src/universal_sdd/__init__.py`, README status and CHANGELOG with one release version. Review docs and examples for obsolete commands.
2. Run the repository CI jobs, the incident and cross-project benchmarks, and build an sdist and wheel from a clean checkout.
3. Inspect archive contents, metadata and entry point; install the wheel in a clean virtual environment and run `sdd --help`. Check secrets and generated artifacts are absent.
4. Publish **that exact verified distribution** to PyPI using a trusted publisher or a scoped project token. Avoid a release number already on PyPI; published files cannot be replaced.
5. Install the published version in a clean environment and recheck the command and metadata. Tag the exact Git commit and create release notes that include the tested boundaries.
6. For a broken release, publish a corrected next version. Never delete or overwrite history as a repair strategy.

For the first upload, register a pending PyPI Trusted Publisher for project `vega-sdd`, owner `teja499-tech`, repository `vega-sdd`, workflow `publish.yml`, environment `pypi`. Then trigger the publish workflow on the verified tag (or dispatch it from the exact verified main commit). PyPI requires exact matching identity. The GitHub repository must configure required status checks, PR reviews and the PyPI trusted-publisher identity explicitly. This source tree ships tests and packaging; repository settings and publishing credentials are managed by the maintainer.
