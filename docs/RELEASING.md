# Releasing Vega SDD

Maintainers publish a version only after source, docs, examples, and the wheel agree on the name, CLI, and version. The distribution name is `vega-sdd`, the command is `sdd`, and the import module remains `universal_sdd` for compatibility.

1. Update `pyproject.toml`, `src/universal_sdd/__init__.py`, README status, current verification guide, and CHANGELOG with one release version. Review every guide/example for obsolete commands and historical claims presented as current.
2. Run the repository CI jobs, the incident and cross-project benchmarks, and build an sdist and wheel from a clean checkout.
3. Inspect archive contents, metadata and entry point; install the wheel in a clean virtual environment and run `sdd --help`. Check secrets and generated artifacts are absent.
4. Merge the release commit to `main`, wait for its required checks to pass, then create and push the matching tag, for example `git tag -s v0.4.0 && git push origin v0.4.0`. The tag must point to a commit contained in `main`, and its version must exactly match `pyproject.toml`.
5. The tag starts `.github/workflows/publish.yml`. That workflow reruns the release checks, builds the distributions, and publishes them to PyPI through the `pypi` environment and Trusted Publishing. It has no manual-dispatch path.
6. Install the published version in a clean environment, recheck the command and metadata, and create immutable GitHub release notes that state the tested boundaries.
7. For a failed workflow with no PyPI upload, fix the cause and rerun the same workflow attempt. If any file reached PyPI or the release is otherwise broken, publish a corrected next version. Never move a published release tag, reuse a version, delete a release to conceal history, or overwrite artifacts.

For the first upload, register a pending PyPI Trusted Publisher for project `vega-sdd`, owner `teja499-tech`, repository `vega-sdd`, workflow `publish.yml`, environment `pypi`. Then push the verified tag. PyPI requires exact matching identity. The GitHub repository must configure required status checks, pull-request rules, and the PyPI trusted-publisher identity explicitly. This source tree ships tests and packaging; repository settings and publishing credentials are managed by the maintainer.
