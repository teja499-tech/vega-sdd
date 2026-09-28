from pathlib import Path

from universal_sdd.adapters.cursor import CursorAdapter
from universal_sdd.adapters.codex import CodexAdapter
from universal_sdd.adapters.claude import ClaudeAdapter
from universal_sdd.adapters.gemini import GeminiAdapter
from universal_sdd.adapters.copilot import CopilotAdapter


def test_cursor_command_is_bounded_and_structured(tmp_path: Path):
    a = CursorAdapter(tmp_path)
    # build_command may consult capabilities, so assert shape only if command exists/falls back.
    cmd = a.build_command("hello", writable=False, mode="plan")
    assert "--output-format" in cmd
    assert "--workspace" in cmd
    assert "--mode" in cmd
    assert "--trust" in cmd
    assert "--force" not in cmd
    assert cmd[cmd.index("--model") + 1] == "auto"
    write_cmd = a.build_command("hello", writable=True, mode="agent")
    assert "--trust" in write_cmd
    assert "--force" not in write_cmd
    assert "--mode" not in write_cmd
    assert write_cmd[write_cmd.index("--model") + 1] == "auto"


def test_codex_command_uses_json_and_full_auto_for_write(tmp_path: Path):
    cmd = CodexAdapter(tmp_path).build_command("hello", writable=True)
    assert cmd[:3] == ["codex", "exec", "--json"]
    assert cmd[3:5] == ["--sandbox", "workspace-write"]
    assert CodexAdapter(tmp_path).build_command("inspect", writable=False)[3:5] == ["--sandbox", "read-only"]


def test_claude_command_uses_stream_json(tmp_path: Path):
    cmd = ClaudeAdapter(tmp_path).build_command("hello", writable=False, mode="plan")
    assert "stream-json" in cmd
    assert "plan" in cmd


def test_gemini_and_copilot_honor_read_write_contract(tmp_path: Path):
    write = GeminiAdapter(tmp_path).build_command("hello", writable=True)
    read = GeminiAdapter(tmp_path).build_command("hello", writable=False)
    assert "--yolo" not in write and "--sandbox" in write and "--sandbox" in read
    assert write[write.index("--approval-mode") + 1] == "auto_edit"
    write_cop = CopilotAdapter(tmp_path).build_command("hello", writable=True)
    assert "--allow-all" not in write_cop
    assert "--no-ask-user" in write_cop
    assert write_cop[write_cop.index("--allow-tool") + 1] == "write"
    read_cop = CopilotAdapter(tmp_path).build_command("hello", writable=False)
    assert "--no-ask-user" in read_cop
    assert "--allow-all" not in read_cop
    assert "--allow-tool" not in read_cop
