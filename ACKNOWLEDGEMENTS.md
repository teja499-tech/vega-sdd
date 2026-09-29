# Acknowledgements

Vega SDD is built in the open and benefits from ideas, tools, and feedback shared by the wider developer-tool community.

## Research and design inspiration

- [ECC](https://github.com/affaan-m/ECC), maintained by [@affaan-m](https://github.com/affaan-m) and its contributors, informed our research into composable roles, skills, review runbooks, progressive disclosure, and cross-agent instruction surfaces. Vega SDD implements its own repository-owned controller, state model, approval boundaries, recovery contracts, and lifecycle authority; it is not an ECC distribution or an official ECC integration.

## Optional integrations

- [Graphify](https://github.com/Graphify-Labs/graphify) provides the optional local code-graph capability used by `sdd graph refresh` and `sdd graph query`. Vega keeps `.sdd/` as canonical state and continues without Graphify when it is unavailable.
- [Headroom](https://github.com/headroomlabs-ai/headroom) provides the optional context-compression capability used for selected context packs and check logs. Vega retains originals and continues without Headroom when it is unavailable.

These projects retain their own names, trademarks, copyrights, and licenses. Acknowledgement does not imply sponsorship, endorsement, partnership, or responsibility for Vega SDD.

## Open-source foundations

Vega SDD is made possible by the Python and Git ecosystems and directly uses excellent open-source libraries including [Typer](https://github.com/fastapi/typer), [Rich](https://github.com/Textualize/rich), [Pydantic](https://github.com/pydantic/pydantic), [PyYAML](https://github.com/yaml/pyyaml), and [pytest](https://github.com/pytest-dev/pytest).

## Contributors

Thank you to everyone who reports issues, proposes improvements, reviews changes, improves documentation, or contributes code. GitHub's [contributors page](https://github.com/teja499-tech/vega-sdd/graphs/contributors) is the durable record of repository contributions.

If a credit is missing or inaccurate, please open an issue with the relevant project, contribution, and preferred attribution.
