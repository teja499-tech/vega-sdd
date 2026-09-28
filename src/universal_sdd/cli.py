from __future__ import annotations

import json
import os
import sys
import time
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .adapters import get_adapter
from .adapters.base import UNRESTRICTED_ENV
from .artifacts import project_context, write_architecture, write_spec_bundle
from .json_utils import extract_json, parse_structured
from .journal import Journal
from .models import (
    AgentName,
    ArchitectureDecision,
    ChangeRequest,
    DecisionStatus,
    PRIMARY_AGENTS,
    ProductModel,
    ProjectKind,
    RunStatus,
    SDDConfig,
    SpecBundle,
)
from .orchestrator import analyze_change, apply_change, ask_project, invoke_agent, request_pause, retry_task, run_development
from .prompts import (
    architecture_prompt,
    ask_architect_prompt,
    product_discovery_prompt,
    spec_bundle_prompt,
)
from .repository import materialize_repository_view, summarize_repository
from .scaffold import refresh_scaffold, write_scaffold
from .status import metrics, publish_status, render_status
from .storage import (
    SDDPaths,
    single_writer,
    dump_yaml,
    load_config,
    load_project_state,
    load_yaml,
    save_config,
    save_project_state,
)
from .traceability import validate_traceability

app = typer.Typer(help="Vega SDD — interactive Spec Driven Development control plane.", no_args_is_help=True)
agent_app = typer.Typer(help="Inspect or change the primary coding agent.")
app.add_typer(agent_app, name="agent")
console = Console()


def _root(path: Path) -> Path:
    return path.resolve()


def _fail(message: str, code: int = 1) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code)


def _event_printer(event) -> None:
    msg = event.message.strip()
    if msg:
        if len(msg) > 220:
            msg = msg[:217] + "..."
        console.print(f"[dim]{event.type}[/dim] {msg}")


_JSON_RETRY_PREFIX = (
    "CRITICAL CONTROLLER RETRY: Your previous reply was not valid JSON. "
    "Do not explain. Do not use markdown fences. The first character of the "
    "response must be '{' or '['. Return ONLY the required JSON value.\n\n"
)


def _persist_agent_text(paths: SDDPaths, name: str, text: str) -> None:
    paths.runtime.mkdir(parents=True, exist_ok=True)
    (paths.runtime / f"{name}.txt").write_text(text or "", encoding="utf-8")


def _require_model(
    adapter,
    prompt: str,
    validate,
    label: str,
    paths: SDDPaths,
    *,
    invocation_root: Path | None = None,
):
    """Run a read-only plan call and parse structured JSON, retrying once."""
    # Cursor --mode plan is for analysis/proposals and often returns prose.
    # Structured init payloads use ask (read-only) so the model can emit JSON.
    agent_root = invocation_root or paths.root
    result = invoke_agent(adapter, prompt, agent_root, writable=False, mode="ask", on_event=_event_printer)
    if not result.success:
        _persist_agent_text(paths, label.replace(" ", "-"), result.text)
        _fail(result.text or f"{label} agent failed")
    try:
        return parse_structured(result.text, validate)
    except Exception:
        _persist_agent_text(paths, label.replace(" ", "-"), result.text)
        console.print(f"[yellow]{label} did not return valid JSON; retrying once.[/yellow]")
        retry = invoke_agent(adapter, _JSON_RETRY_PREFIX + prompt, agent_root, writable=False, mode="ask", on_event=_event_printer)
        _persist_agent_text(paths, label.replace(" ", "-") + "-retry", retry.text)
        if not retry.success:
            _fail(retry.text or f"{label} retry failed")
        try:
            return parse_structured(retry.text, validate)
        except Exception as exc:
            _fail(f"Could not parse {label} output: {exc}")


def _select_architecture(adapter, prd: str, decisions: list[ArchitectureDecision], yes: bool, root: Path) -> list[ArchitectureDecision]:
    for d in decisions:
        console.print()
        console.rule(f"{d.id} · {d.category.replace('_', ' ').title()}")
        console.print(d.question)
        if d.rationale:
            console.print(f"[dim]{d.rationale}[/dim]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", width=3)
        table.add_column("Option")
        table.add_column("Fit")
        table.add_column("Summary")
        for i, opt in enumerate(d.options, 1):
            table.add_row(str(i), opt.name, opt.fit or "-", opt.summary)
        console.print(table)
        if d.recommendation:
            console.print(f"Recommendation: [bold]{d.recommendation}[/bold] — {d.recommendation_reason}")

        if yes:
            chosen = d.recommendation or (d.options[0].name if d.options else None)
            if chosen:
                d.selected = chosen
                d.selected_reason = "Accepted automatically via --yes"
                d.status = DecisionStatus.selected
            else:
                d.status = DecisionStatus.deferred
            continue

        while True:
            raw = typer.prompt("Choose option number, 'a' ask architect, 'o' other, or 'd' defer", default="1")
            if raw.lower() == "a":
                q = typer.prompt("Question for architect")
                ctx = f"PRD:\n{prd}\n\nArchitecture decision:\n{json.dumps(d.model_dump(mode='json'), indent=2)}"
                ans = invoke_agent(adapter, ask_architect_prompt(q, ctx), root, writable=False, mode="plan")
                console.print(Panel(ans.text or "No response", title="Architect"))
                continue
            if raw.lower() == "d":
                d.status = DecisionStatus.deferred
                break
            if raw.lower() == "o":
                d.selected = typer.prompt("Technology / option")
                d.selected_reason = typer.prompt("Why are you choosing it?", default="User-selected alternative")
                d.status = DecisionStatus.selected
                break
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(d.options):
                    d.selected = d.options[idx].name
                    d.selected_reason = typer.prompt("Decision note", default="Selected during SDD architecture workshop")
                    d.status = DecisionStatus.selected
                    break
            except ValueError:
                pass
            console.print("[yellow]Enter a listed number, a, o, or d.[/yellow]")
    return decisions


@app.command()
@single_writer
def init(
    prd: Path = typer.Option(Path("PRD.md"), "--prd", help="Path to product requirements Markdown/text."),
    agent: Optional[AgentName] = typer.Option(None, "--agent", help="Initial coding agent."),
    project_kind: Optional[ProjectKind] = typer.Option(None, "--project-kind", help="New or existing codebase."),
    root: Path = typer.Option(Path("."), "--root", help="Project root."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept recommended defaults non-interactively."),
    force: bool = typer.Option(False, "--force", help="Reinitialize an existing .sdd directory."),
) -> None:
    """Initialize SDD from a PRD through product discovery and an architecture workshop."""
    root = _root(root)
    paths = SDDPaths(root)
    prd_path = prd if prd.is_absolute() else root / prd
    if not prd_path.exists():
        _fail(f"PRD not found: {prd_path}")
    prd_text = prd_path.read_text(encoding="utf-8")
    if not prd_text.strip():
        _fail("PRD is empty.")

    console.print(Panel.fit("Vega SDD · Project Initialization", subtitle=f"v{__version__}"))
    if agent is None:
        if yes:
            agent = AgentName.cursor
        else:
            raw = typer.prompt("Initial coding agent (cursor/codex/claude/gemini/copilot)", default="cursor")
            try:
                agent = AgentName(raw.lower())
            except ValueError:
                _fail(f"Unsupported agent: {raw}")
    has_code = any(p.name not in {prd_path.name, ".git", ".sdd", ".sdd-controller.lock"} and not p.name.startswith(".sdd-backup-") for p in root.iterdir())
    if project_kind is None:
        if yes:
            project_kind = ProjectKind.existing if has_code else ProjectKind.new
        else:
            raw = typer.prompt("Project type (new/existing)", default="existing" if has_code else "new")
            project_kind = ProjectKind(raw.lower())

    if paths.config_file.exists() and not force:
        existing = load_project_state(paths)
        if existing.initialized:
            _fail("SDD is already initialized. Use --force only if you intentionally want to regenerate setup artifacts.")

    if force and paths.sdd.exists() and load_project_state(paths).initialized:
        backup = root / f".sdd-backup-{uuid.uuid4().hex[:8]}"
        shutil.copytree(paths.sdd, backup)
        shutil.rmtree(paths.sdd)
        paths = SDDPaths(root)

    write_scaffold(root)
    config = SDDConfig(
        project_name=root.name,
        project_kind=project_kind,
        prd_path=str(prd_path.relative_to(root) if prd_path.is_relative_to(root) else prd_path),
        primary_agent=agent,
    )
    save_config(paths, config)
    state = load_project_state(paths)
    state.initialized = False
    state.run_status = RunStatus.initializing
    save_project_state(paths, state)

    def _fail_init(message: str, code: int = 1) -> None:
        failed = load_project_state(paths)
        failed.initialized = False
        failed.run_status = RunStatus.failed
        save_project_state(paths, failed)
        _fail(message, code)

    finished = False
    init_workspace = tempfile.TemporaryDirectory(prefix="vega-sdd-init-")
    invocation_root = Path(init_workspace.name)
    try:
        # Initialization runs outside the target repository so pre-existing agent
        # rules and project-local skills cannot execute before the user approves
        # their capability hash during `sdd project setup`.
        write_scaffold(invocation_root, force=True)
        (invocation_root / "PRD.md").write_text(prd_text, encoding="utf-8")
        source_view_note = ""
        if project_kind == ProjectKind.existing:
            source_view_note = materialize_repository_view(root, invocation_root)
        adapter = get_adapter(agent, invocation_root)
        caps = adapter.capabilities()
        if not caps.installed:
            _fail_init(f"{agent.value} CLI is not installed or not on PATH. Scaffold/config were created; install the agent and rerun `sdd init`.")
        console.print(f"Agent: [bold]{agent.value}[/bold] ({caps.version or 'version unknown'})")

        repo_summary = summarize_repository(root) if project_kind == ProjectKind.existing else ""
        if source_view_note:
            repo_summary = source_view_note + "\n" + repo_summary
        console.print("\n[bold]1/4 Product discovery[/bold]")
        product = _require_model(
            adapter,
            product_discovery_prompt(prd_text, repo_summary),
            ProductModel.model_validate,
            "product discovery",
            paths,
            invocation_root=invocation_root,
        )

        from .clarifications import record_architecture_decisions, record_product_questions
        answers: list[tuple[str, str]] = []
        if product.open_questions:
            console.print(f"Found {len(product.open_questions)} material clarification question(s).")
            for question in product.open_questions:
                if yes:
                    answers.append((question, "Deferred"))
                else:
                    answers.append((question, typer.prompt(question, default="defer")))
            record_product_questions(paths, product, answers)
        clarifications = [f"{qid}: {q}\nA: {a}" for qid, (q, a) in ((f"Q{i}", pair) for i, pair in enumerate(answers, 1))]
        augmented_prd = prd_text + ("\n\n# SDD Clarifications\n" + "\n\n".join(clarifications) if clarifications else "")

        console.print("\n[bold]2/4 Architecture workshop[/bold]")
        def _validate_decisions(raw):
            if not isinstance(raw, list):
                raise ValueError("Architecture output must be a JSON array")
            return [ArchitectureDecision.model_validate(x) for x in raw]
        decisions = _require_model(
            adapter,
            architecture_prompt(augmented_prd, repo_summary),
            _validate_decisions,
            "architecture",
            paths,
            invocation_root=invocation_root,
        )
        decisions = _select_architecture(adapter, augmented_prd, decisions, yes, invocation_root)
        write_architecture(paths, decisions)
        record_architecture_decisions(paths, decisions)

        deferred = [d for d in decisions if d.status == DecisionStatus.deferred]
        if deferred:
            console.print(f"[yellow]{len(deferred)} architecture decision(s) remain deferred. Specs will record them as unresolved.[/yellow]")

        console.print("\n[bold]3/4 Specification generation[/bold]")
        bundle = _require_model(
            adapter,
            spec_bundle_prompt(augmented_prd, decisions, repo_summary, skill_root=invocation_root),
            SpecBundle.model_validate,
            "specification bundle",
            paths,
            invocation_root=invocation_root,
        )
        try:
            write_spec_bundle(paths, bundle)
        except ValueError as exc:
            _fail_init(str(exc), 2)
        from .clarifications import merge_open_questions
        merge_open_questions(paths, bundle.product.open_questions)

        report = validate_traceability(paths)
        if not report.ok:
            console.print("[red]Traceability validation failed.[/red]")
            for e in report.errors:
                console.print(f"  • {e}")
            _fail_init("Traceability validation failed.", 2)
        Journal(paths.event_log).append("project_initialized", agent=agent.value, requirements=len(bundle.requirements), features=len(bundle.features))
        ready = load_project_state(paths)
        ready.initialized = True
        ready.run_status = RunStatus.ready
        ready.artifacts_generated = True
        save_project_state(paths, ready)
        publish_status(paths)
        finished = True

        from .documentation import check_docs
        doc_gaps = check_docs(paths)
        console.print(f"Human docs: .sdd/docs/README.md ({len(doc_gaps)} documentation gap(s); run sdd docs check)")
        console.print("\n[bold]4/4 Readiness review[/bold]")
        console.print(f"✓ Requirements: {len(bundle.requirements)}")
        console.print(f"✓ Features: {len(bundle.features)}")
        console.print(f"✓ Architecture decisions: {len(decisions)}")
        console.print(f"✓ Traceability: valid ({len(report.warnings)} warning(s))")
        if bundle.product.open_questions or deferred:
            console.print("[yellow]Project contains unresolved questions/decisions. Review before autonomous development.[/yellow]")
        else:
            console.print("[green]Project is ready for implementation.[/green]")
        console.print("Inspect: [bold]sdd status[/bold], [bold]sdd requirements[/bold], [bold]sdd architecture[/bold], [bold]sdd roadmap[/bold], [bold]sdd verify[/bold]")
        if agent == AgentName.mock:
            console.print("Next: [bold]sdd start[/bold] (the mock exercises lifecycle only; it does not build application code)")
        else:
            console.print(
                "Next: [bold]sdd project setup[/bold], review/commit the generated baseline, "
                "then [bold]sdd repo branch <scope>[/bold] and [bold]sdd start --max-tasks 1[/bold]."
            )
    finally:
        init_workspace.cleanup()
        if not finished:
            failed = load_project_state(paths)
            failed.initialized = False
            failed.run_status = RunStatus.failed
            save_project_state(paths, failed)


@app.command("scaffold")
@single_writer
def scaffold_cmd(
    root: Path = typer.Option(Path("."), "--root"),
    force: bool = typer.Option(False, "--force", help="Overwrite customized skills and roles, not only stubs."),
) -> None:
    """Refresh roles, skills, and IDE commands in an existing project. Does not rewrite specs."""
    report = refresh_scaffold(_root(root), refresh=True, force=force)
    for action, rows in report.items():
        if not rows:
            continue
        console.print(f"[bold]{action}[/bold] ({len(rows)})")
        for rel in rows:
            console.print(f"  {rel}")
    if not any(report.values()):
        console.print("Scaffold already current.")


@app.command()
def doctor(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Inspect SDD and coding-agent readiness."""
    root = _root(root)
    table = Table(title="Vega SDD Doctor")
    table.add_column("Agent")
    table.add_column("Installed")
    table.add_column("Version")
    table.add_column("Capabilities")
    for name in PRIMARY_AGENTS:
        caps = get_adapter(name, root).capabilities()
        features = ", ".join(k for k, v in {
            "stream": caps.streaming, "resume": caps.resume, "interrupt": caps.interrupt, "structured": caps.structured_output
        }.items() if v)
        table.add_row(name.value, "yes" if caps.installed else "no", caps.version or "-", features)
    console.print(table)
    paths = SDDPaths(root)
    if paths.config_file.exists():
        from .clarifications import unresolved_material
        cfg = load_config(paths)
        state = load_project_state(paths)
        console.print(f"Configured primary agent: [bold]{cfg.primary_agent.value}[/bold]")
        console.print(f"SDD state: {state.run_status.value}")
        if not cfg.test_command and cfg.primary_agent != AgentName.mock and not (root / ".sdd/workspace.yaml").exists():
            console.print("[yellow]Missing test_command and workspace policy. Run `sdd project setup`.[/yellow]")
        if not (root / ".sdd/workspace.yaml").exists() and cfg.primary_agent != AgentName.mock:
            console.print("[yellow]No approved workspace policy. Real-agent runs require `sdd project setup`.[/yellow]")
        open_qs = unresolved_material(paths)
        if open_qs:
            console.print(f"[yellow]{len(open_qs)} unresolved clarification(s). Run `sdd clarify` or start with --accept-deferred.[/yellow]")
        if shutil.which("docker") is None:
            console.print("[dim]docker not on PATH (optional; needed for compose-based projects).[/dim]")
        console.print(f"Graphify: {'installed' if shutil.which('graphify') else 'missing — sdd graph refresh needs the Graphify CLI'}")
        try:
            import headroom  # noqa: F401
            headroom_state = "installed"
            headroom_ok = True
        except ImportError:
            headroom_state = "missing — prompts stay uncompressed until headroom-ai is installed"
            headroom_ok = False
        console.print(f"Headroom: {headroom_state}")
        if not shutil.which("graphify") or not headroom_ok:
            console.print(
                "[yellow]Token efficiency degraded: install Graphify and headroom-ai so "
                "ask/change/task packs stay scoped and compressed.[/yellow]"
            )
        if cfg.review_agent:
            console.print(f"Review agent: [bold]{cfg.review_agent.value}[/bold]")
        else:
            console.print("Review agent: same as primary (isolated self-review, not an independent model)")
        if not cfg.enable_headroom:
            console.print("Headroom compression: disabled in config")
        if cfg.allow_unrestricted_agent:
            console.print("[yellow]allow_unrestricted_agent is on: writable agents receive vendor auto-approve flags. Keep the run isolated.[/yellow]")
        else:
            console.print("Unrestricted agent flags: off (set allow_unrestricted_agent or pass --allow-unrestricted on start)")
    else:
        console.print("SDD not initialized in this directory.")


@agent_app.command("list")
def agent_list(root: Path = typer.Option(Path("."), "--root")) -> None:
    root = _root(root)
    paths = SDDPaths(root)
    current = load_config(paths).primary_agent if paths.config_file.exists() else None
    for name in PRIMARY_AGENTS:
        caps = get_adapter(name, root).capabilities()
        marker = "*" if current == name else " "
        console.print(f"{marker} {name.value:8} {'installed' if caps.installed else 'missing':9} {caps.version or ''}")


@agent_app.command("use")
@single_writer
def agent_use(name: AgentName, root: Path = typer.Option(Path("."), "--root")) -> None:
    root = _root(root)
    paths = SDDPaths(root)
    config = load_config(paths)
    caps = get_adapter(name, root).capabilities()
    if not caps.installed:
        _fail(f"{name.value} is not installed/on PATH.")
    old = config.primary_agent
    config.primary_agent = name
    save_config(paths, config)
    Journal(paths.event_log).append("primary_agent_changed", old=old.value, new=name.value)
    console.print(f"Primary agent changed: {old.value} → [bold]{name.value}[/bold]")


@app.command()
def status(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Show durable implementation and verification progress."""
    paths = SDDPaths(_root(root))
    if not paths.config_file.exists():
        _fail("SDD is not initialized.")
    publish_status(paths)
    m = metrics(paths)
    state = load_project_state(paths)
    table = Table(title=f"SDD Status · {load_config(paths).project_name}")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Run status", state.run_status.value)
    table.add_row("Overall", f"{m.overall_pct:.1f}%")
    table.add_row("Specification", f"{m.spec_pct:.1f}%")
    table.add_row("Implementation", f"{m.implementation_pct:.1f}%")
    table.add_row("Verification", f"{m.verification_pct:.1f}%")
    table.add_row("Requirements verified", f"{m.requirements_verified}/{m.requirements_total}")
    table.add_row("Tasks verified", f"{m.tasks_verified}/{m.tasks_total}")
    table.add_row("Current", f"{state.current_feature or '-'} / {state.current_task or '-'}")
    from .tokens import savings_summary
    saved = savings_summary(paths)
    if saved["events"]:
        table.add_row("Context saved", f"{saved['saved_chars']} chars / {saved['events']} packs")
    console.print(table)
    console.print(f"Status file: {paths.status_file.relative_to(paths.root)}")


@app.command()
def watch(
    root: Path = typer.Option(Path("."), "--root"),
    interval: float = typer.Option(2.0, "--interval", min=0.5),
) -> None:
    """Continuously refresh SDD status until interrupted."""
    paths = SDDPaths(_root(root))
    try:
        while True:
            console.clear()
            console.print(render_status(paths))
            console.print("[dim]Ctrl+C to stop watching. Development continues if running elsewhere.[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        return


@app.command()
def start(
    root: Path = typer.Option(Path("."), "--root"),
    max_tasks: Optional[int] = typer.Option(None, "--max-tasks", min=1, help="Pause after N verified tasks."),
    accept_deferred: bool = typer.Option(False, "--accept-deferred", help="Sign deferred clarifications as accepted defaults."),
    allow_unrestricted: bool = typer.Option(False, "--allow-unrestricted", help="Opt in to vendor auto-approve flags for this run only."),
) -> None:
    """Run autonomous task implementation/review/repair in the foreground."""
    root = _root(root)
    if allow_unrestricted:
        os.environ[UNRESTRICTED_ENV] = "1"
        console.print("[yellow]Unrestricted agent flags enabled for this process. Isolate the workspace.[/yellow]")
    console.print("Starting SDD development. Ctrl+C requests a safe pause.")
    try:
        state = run_development(root, max_tasks=max_tasks, on_event=_event_printer, accept_deferred=accept_deferred)
    except RuntimeError as exc:
        _fail(str(exc), 2)
    console.print(f"Run ended with state: [bold]{state.run_status.value}[/bold]")
    status(root=root)
    if state.run_status in {RunStatus.blocked, RunStatus.failed}:
        raise typer.Exit(2)


@app.command()
def resume(
    root: Path = typer.Option(Path("."), "--root"),
    max_tasks: Optional[int] = typer.Option(None, "--max-tasks", min=1),
    accept_deferred: bool = typer.Option(False, "--accept-deferred"),
    allow_unrestricted: bool = typer.Option(False, "--allow-unrestricted"),
) -> None:
    """Resume from durable repository state; no prior chat context is required."""
    root = _root(root)
    start(root=root, max_tasks=max_tasks, accept_deferred=accept_deferred, allow_unrestricted=allow_unrestricted)


@app.command()
def pause(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Request a pause. Active foreground work stops at the next safe task boundary."""
    state = request_pause(_root(root))
    console.print(f"Pause requested. Current: {state.current_feature or '-'} / {state.current_task or '-'}")


@app.command()
def verify(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Validate requirement/feature/task traceability."""
    paths = SDDPaths(_root(root))
    report = validate_traceability(paths)
    if report.ok:
        console.print(f"[green]Traceability PASS[/green] ({len(report.warnings)} warning(s))")
    else:
        console.print("[red]Traceability FAIL[/red]")
    for e in report.errors:
        console.print(f"[red]ERROR[/red] {e}")
    for w in report.warnings:
        console.print(f"[yellow]WARN[/yellow] {w}")
    if not report.ok:
        raise typer.Exit(2)


@single_writer
def _intervention_answer(root: Path, question: str) -> str:
    paths = SDDPaths(root)
    config = load_config(paths)
    from .workspace import require_approved_capabilities
    require_approved_capabilities(root, config.primary_agent)
    adapter = get_adapter(config.primary_agent, root)
    result = invoke_agent(adapter, ask_architect_prompt(question, project_context(paths)), root, writable=False, mode="plan")
    if not result.success:
        raise RuntimeError(result.text or "Architect intervention failed")
    return result.text


@app.command()
def intervene(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Open an interactive architect conversation grounded in current repo state."""
    root = _root(root)
    console.print("Architect intervention session. Type `exit` to leave, `change: ...` to analyze a correction/change.")
    while True:
        try:
            question = typer.prompt("architect>")
        except (EOFError, KeyboardInterrupt):
            break
        if question.strip().lower() in {"exit", "quit", "/exit"}:
            break
        if question.lower().startswith("change:"):
            desc = question.split(":", 1)[1].strip()
            cr = analyze_change(root, desc)
            _print_change(cr)
            if cr.requires_approval:
                console.print("Run `sdd change \"...\"` to explicitly approve/apply it.")
            continue
        try:
            answer = _intervention_answer(root, question)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            continue
        console.print(Panel(answer or "No response", title="Architect"))


def _print_change(cr: ChangeRequest) -> None:
    console.print(Panel.fit(
        f"Classification: [bold]{cr.classification}[/bold]\n"
        f"Affected requirements: {', '.join(cr.affected_requirements) or '-'}\n"
        f"Affected features: {', '.join(cr.affected_features) or '-'}\n"
        f"Tasks that will be invalidated: {', '.join(cr.affected_tasks) or '-'}\n"
        f"Approval required: {'yes' if cr.requires_approval else 'no'}\n"
        f"Proposed: {'; '.join(cr.proposed_changes) or '-'}",
        title=cr.id,
    ))
    if cr.affected_tasks:
        console.print("[yellow]Resume will re-run only the invalidated tasks and their dependents.[/yellow]")


@app.command()
def change(
    description: str = typer.Argument(..., help="Problem or desired change in natural language."),
    root: Path = typer.Option(Path("."), "--root"),
    approve: bool = typer.Option(False, "--approve", help="Explicitly approve specification/architecture mutation."),
) -> None:
    """Analyze a problem, classify it, and safely repair or reconcile affected specs."""
    root = _root(root)
    try:
        cr = analyze_change(root, description)
    except (RuntimeError, ValueError) as exc:
        _fail(str(exc), 2)
    _print_change(cr)
    if cr.requires_approval and not approve:
        approve = typer.confirm("This changes approved requirements/specs/architecture. Approve?", default=False)
    if cr.requires_approval and not approve:
        console.print(f"Change recorded as proposed: .sdd/changes/{cr.id}.yaml")
        console.print("Re-run with --approve after reviewing the invalidated-task preview.")
        return
    cr.approved = True
    cr.status = "approved"
    from .reconcile import nested_cursor_agent
    if nested_cursor_agent() and cr.classification != "implementation_defect":
        console.print(
            "[yellow]Warning: nested Cursor agent detected. Reconcile may hang; "
            "prefer a host terminal for `sdd change --approve`.[/yellow]"
        )
    if cr.classification != "implementation_defect":
        console.print("[cyan]Reconciling approved change (slice merge, 300s timeout)…[/cyan]")
    try:
        applied = apply_change(root, cr, on_event=_event_printer)
    except RuntimeError as exc:
        _fail(str(exc), 2)
    console.print(f"[green]{applied.id} applied.[/green]")
    console.print("Review `sdd status`, then `sdd resume` when ready.")


def _cat(path: Path, title: str) -> None:
    if not path.exists():
        _fail(f"{title} not generated yet.")
    console.print(Panel(path.read_text(encoding="utf-8"), title=title))


@app.command()
def roadmap(root: Path = typer.Option(Path("."), "--root")) -> None:
    paths = SDDPaths(_root(root))
    _cat(paths.sdd / "roadmap.md", "Roadmap")


@app.command()
def requirements(root: Path = typer.Option(Path("."), "--root")) -> None:
    paths = SDDPaths(_root(root))
    _cat(paths.product / "requirements.md", "Requirements")


@app.command()
def architecture(root: Path = typer.Option(Path("."), "--root")) -> None:
    paths = SDDPaths(_root(root))
    _cat(paths.architecture / "decisions.md", "Architecture")


@app.command()
def feature(
    feature_id: str,
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    paths = SDDPaths(_root(root))
    matches = list(paths.specs.glob(f"{feature_id}-*"))
    if not matches:
        _fail(f"Feature not found: {feature_id}")
    text = ""
    for name in ["spec.md", "tasks.md", "state.yaml"]:
        p = matches[0] / name
        if p.exists():
            text += f"\n## {name}\n{p.read_text(encoding='utf-8')}\n"
    console.print(Panel(text, title=feature_id))


graph_app = typer.Typer(help="Refresh and query the Graphify knowledge graph.")
app.add_typer(graph_app, name="graph")


@graph_app.command("refresh")
@single_writer
def graph_refresh(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Write the traceability corpus and run graphify (or graphify update)."""
    from .graphify_index import refresh_knowledge_graph
    result = refresh_knowledge_graph(SDDPaths(_root(root)))
    console.print(f"Corpus: {result.get('corpus')}")
    if not result.get("installed"):
        console.print("[yellow]graphify CLI is not installed. Corpus was written; the knowledge graph was not built.[/yellow]")
        return
    console.print(result.get("command") or "graphify")
    if result.get("exit_code"):
        console.print(result.get("output") or "graphify failed")
        raise typer.Exit(2)
    console.print(f"Graph: {result.get('graph') or 'graphify-out/graph.json'}")


@graph_app.command("query")
def graph_query(
    question: str = typer.Argument(...),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Return a scoped Graphify subgraph for a question."""
    from .graphify_index import query_knowledge_graph
    text = query_knowledge_graph(_root(root), question)
    if not text:
        _fail("No Graphify subgraph. Install graphify and run `sdd graph refresh`.")
    console.print(text)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Project question grounded in specs, ADRs, and the project graph."),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Read-only project copilot. Does not mutate the plan."""
    try:
        answer = ask_project(_root(root), question)
    except RuntimeError as exc:
        _fail(str(exc), 2)
    console.print(Panel(answer or "No response", title="Project copilot"))


@app.command()
@single_writer
def clarify(
    clarification_id: Optional[str] = typer.Argument(None, help="Clarification id such as Q1 or ARCH-001."),
    answer: Optional[str] = typer.Option(None, "--answer", help="Answer to record."),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Resolve material questions that block `sdd start`."""
    from .clarifications import answer_clarification, load_clarifications, unresolved_material
    paths = SDDPaths(_root(root))
    if not clarification_id:
        items = unresolved_material(paths) or load_clarifications(paths)
        if not items:
            console.print("No clarifications recorded.")
            return
        for item in items:
            console.print(f"[bold]{item.id}[/bold] ({item.status}) {item.question}")
            if item.answer:
                console.print(f"  {item.answer}")
        return
    if not answer:
        answer = typer.prompt("Answer")
    try:
        item = answer_clarification(paths, clarification_id, answer)
    except ValueError as exc:
        _fail(str(exc))
    console.print(f"[green]{item.id} answered.[/green]")


task_app = typer.Typer(help="Inspect or recover individual SDD tasks.")
app.add_typer(task_app, name="task")


@task_app.command("retry")
def task_retry(
    task_id: str,
    keep_code: bool = typer.Option(True, "--keep-code/--wipe-status", help="Keep working-tree code and re-verify."),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Re-queue a failed task without wiping uncommitted implementation."""
    try:
        task = retry_task(_root(root), task_id, keep_code=keep_code)
    except RuntimeError as exc:
        _fail(str(exc), 2)
    mode = "implemented (keep code, re-verify)" if keep_code else "pending (re-implement)"
    console.print(f"{task.id} queued as {mode}. Run `sdd resume`.")


@app.command("log")
def log_cmd(
    root: Path = typer.Option(Path("."), "--root"),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    paths = SDDPaths(_root(root))
    rows = Journal(paths.event_log).read(limit)
    for row in rows:
        console.print(f"[dim]{row.get('timestamp','')}[/dim] {row.get('event','')} {json.dumps({k:v for k,v in row.items() if k not in {'timestamp','event'}}, ensure_ascii=False)}")


if __name__ == "__main__":
    app()


# Human documentation and commit attribution are local, vendor-neutral projections.
docs_app = typer.Typer(help="Generate, inspect, and validate human project documentation.")
app.add_typer(docs_app, name="docs")

@docs_app.command("refresh")
@single_writer
def docs_refresh(root: Path = typer.Option(Path("."), "--root"), enrich: bool = typer.Option(False, "--enrich", help="Ask the selected agent to document approved intent and inspect existing code read-only.")) -> None:
    """Regenerate documentation without changing approved specifications."""
    from .documentation import render_docs
    from .history import render_history
    paths = SDDPaths(_root(root))
    if enrich:
        from .documentation import CONTRACT
        from .models import DesignDocument
        from .history import snapshot_specs
        config = load_config(paths)
        from .workspace import require_approved_capabilities
        require_approved_capabilities(paths.root, config.primary_agent)
        bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
        prompt = (
            "You are a technical writer working read-only. Marker: HUMAN_DESIGN_DOCUMENTS_JSON\n"
            "Return ONLY a JSON object mapping document keys to DesignDocument objects.\n"
            "Each has status (draft/documented/not_applicable), summary, sections (heading to Markdown prose), sources (list), gaps (list), not_applicable_reason.\n"
            "Supply every key and exact heading from the contract. Write detailed project-specific designs, tables and diagrams where useful.\n"
            "Inspect relevant code read-only. Distinguish observed current behavior, approved target design, assumptions and unknowns.\n"
            "Never authorize new intent, invent commands/schema/owners/results, or claim filenames prove behavior. Cite actual files and approved requirement/ADR IDs.\n"
            "Put unknowns and contradictions in gaps and use draft status. documented requires complete sections, sources and no gaps.\n"
            "For a new project use planned design. For an existing or full application document as-is, to-be, compatibility, migration and rollback.\n"
            + "Contract: " + json.dumps(CONTRACT)
            + "\nProject kind: " + config.project_kind.value
            + "\nCanonical bundle: " + bundle.model_dump_json()
            + "\nApproved ADRs: " + json.dumps(load_yaml(paths.architecture_decisions_file, []))
            + "\nRepository inventory (not proof of behavior): " + summarize_repository(paths.root)
        )
        result = invoke_agent(get_adapter(config.primary_agent, paths.root), prompt, paths.root, writable=False, mode="plan", on_event=_event_printer)
        if not result.success:
            _fail(result.text or "Documentation agent failed; canonical documents unchanged")
        try:
            raw = extract_json(result.text)
            if not isinstance(raw, dict) or set(raw) != set(CONTRACT):
                raise ValueError("Expected exactly the documented design keys")
            documents = {key: DesignDocument.model_validate(value) for key, value in raw.items()}
        except Exception as exc:
            _fail(f"Invalid design response; documents unchanged: {exc}")
        bundle.design_documents = documents
        dump_yaml(paths.spec_bundle_file, bundle)
        snapshot_specs(paths)
        Journal(paths.event_log).append("documentation_updated", summary="Agent-generated descriptive design refreshed; no product or architecture approval implied")
    findings = render_docs(paths)
    render_history(paths)
    console.print("Documentation: .sdd/docs/README.md")
    for finding in findings:
        console.print(f"Gap: {finding}")

@docs_app.command("check")
def docs_check(root: Path = typer.Option(Path("."), "--root")) -> None:
    """Check presence, required sections, unresolved gaps, and source freshness."""
    from .documentation import check_docs
    findings = check_docs(SDDPaths(_root(root)))
    for finding in findings:
        console.print(finding)
    if findings:
        raise typer.Exit(2)
    console.print("Structural documentation checks passed; semantic review is still required.")

@app.command("changelog")
def changelog(root: Path = typer.Option(Path("."), "--root")) -> None:
    _cat(SDDPaths(_root(root)).sdd / "CHANGELOG.md", "Human change history")

@app.command("link-commit")
@single_writer
def link_commit_cmd(
    task: str,
    commit: str = typer.Option(..., "--commit"),
    summary: str = typer.Option(..., "--summary"),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Attach an existing local commit to a task; never create or push commits."""
    from .history import link_commit
    try:
        record = link_commit(SDDPaths(_root(root)), task, commit, summary)
    except ValueError as exc:
        _fail(str(exc))
    console.print(f"Linked {record['sha']} to {task}")

# Add composable project/repository/delivery operations.
from .lifecycle_cli import register as _register_lifecycle
_register_lifecycle(app)
