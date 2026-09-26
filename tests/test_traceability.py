from pathlib import Path

from universal_sdd.models import Feature, Requirement, Task
from universal_sdd.storage import SDDPaths, dump_yaml
from universal_sdd.traceability import validate_traceability


def test_traceability_detects_unmapped_must_requirement(tmp_path: Path):
    paths = SDDPaths(tmp_path)
    paths.ensure()
    dump_yaml(paths.requirements_file, [Requirement(id="REQ-X-001", title="X", statement="The system shall X.")])
    dump_yaml(paths.features_file, [Feature(id="F001", name="Foundation", summary="", tasks=[])])
    report = validate_traceability(paths)
    assert not report.ok
    assert any("not assigned" in e for e in report.errors)
    assert any("not mapped" in e for e in report.errors)


def test_traceability_passes_valid_graph(tmp_path: Path):
    paths = SDDPaths(tmp_path)
    paths.ensure()
    req = Requirement(id="REQ-X-001", title="X", statement="The system shall X.", acceptance_criteria=["AC-X-001: X works"])
    task = Task(id="TASK-F001-001", feature_id="F001", title="X", description="Implement X", implements=[req.id], verification=["test X"])
    feature = Feature(id="F001", name="X", summary="", requirements=[req.id], tasks=[task])
    dump_yaml(paths.requirements_file, [req])
    dump_yaml(paths.features_file, [feature])
    report = validate_traceability(paths)
    assert report.ok, report.errors
