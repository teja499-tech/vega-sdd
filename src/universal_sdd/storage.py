from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from .models import ProjectState, SDDConfig, utcnow

T = TypeVar("T", bound=BaseModel)


class SDDPaths:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.sdd = self.root / ".sdd"
        self.product = self.sdd / "product"
        self.architecture = self.sdd / "architecture"
        self.decisions = self.sdd / "decisions"
        self.specs = self.sdd / "specs"
        self.state = self.sdd / "state"
        self.journal = self.sdd / "journal"
        self.runtime = self.sdd / "runtime"
        self.changes = self.sdd / "changes"
        self.evidence = self.sdd / "evidence"
        self.templates = self.sdd / "templates"
        self.agents = self.root / ".agents"
        self.skills = self.agents / "skills"
        self.roles = self.agents / "roles"
        self.scripts = self.agents / "scripts"

    @property
    def config_file(self) -> Path:
        return self.sdd / "config.yaml"

    @property
    def project_state_file(self) -> Path:
        return self.state / "project.yaml"

    @property
    def requirements_file(self) -> Path:
        return self.state / "requirements.yaml"

    @property
    def features_file(self) -> Path:
        return self.state / "features.yaml"

    @property
    def verification_file(self) -> Path:
        return self.state / "verification.yaml"

    @property
    def spec_bundle_file(self) -> Path:
        return self.state / "spec-bundle.yaml"

    @property
    def architecture_decisions_file(self) -> Path:
        return self.state / "architecture-decisions.yaml"

    @property
    def status_file(self) -> Path:
        return self.sdd / "STATUS.md"

    @property
    def event_log(self) -> Path:
        return self.journal / "events.jsonl"

    def ensure(self) -> None:
        for p in [
            self.sdd,
            self.product,
            self.architecture,
            self.decisions,
            self.specs,
            self.state,
            self.journal,
            self.runtime,
            self.changes,
            self.evidence,
            self.templates,
            self.agents,
            self.skills,
            self.roles,
            self.scripts,
        ]:
            p.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".sdd-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dump_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [x.model_dump(mode="json") if isinstance(x, BaseModel) else x for x in data]
    atomic_write(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def load_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        data = data.model_dump(mode="json")
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))


def load_config(paths: SDDPaths) -> SDDConfig:
    data = load_yaml(paths.config_file)
    if not data:
        raise FileNotFoundError("SDD is not initialized. Run `sdd init` first.")
    return SDDConfig.model_validate(data)


def save_config(paths: SDDPaths, config: SDDConfig) -> None:
    config.updated_at = utcnow()
    dump_yaml(paths.config_file, config)


def load_project_state(paths: SDDPaths) -> ProjectState:
    data = load_yaml(paths.project_state_file, {})
    return ProjectState.model_validate(data or {})


def save_project_state(paths: SDDPaths, state: ProjectState) -> None:
    state.updated_at = utcnow()
    dump_yaml(paths.project_state_file, state)


from contextlib import contextmanager
from functools import wraps


@contextmanager
def project_lock(root: Path):
    """OS-held single writer lease. Automatically released on process death."""
    lock = root.resolve() / ".sdd-controller.lock"
    import subprocess
    try:
        common=subprocess.run(['git','rev-parse','--git-common-dir'],cwd=root,capture_output=True,text=True,timeout=5)
        if common.returncode==0:lock=(root/common.stdout.strip()).resolve()/'sdd-controller.lock'
    except (OSError,subprocess.TimeoutExpired):pass
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0); stream.write(b"0"); stream.flush(); stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another SDD controller is active; pause it first") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Another SDD controller is active; pause it first") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def single_writer(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        import inspect
        bound = inspect.signature(fn).bind(*args, **kwargs)
        root = bound.arguments["root"]
        with project_lock(root):
            from .artifacts import recover_projection_transaction
            recover_projection_transaction(SDDPaths(Path(root)))
            return fn(*args, **kwargs)
    return wrapped
