from pathlib import Path

from context_tax.audit import audit, estimate_tokens, suggest_agentignore, categorize
from context_tax.cli import main


def test_estimate_tokens_text():
    raw = b"abcd" * 100  # 400 chars -> ~100 tokens
    assert estimate_tokens(raw, is_binary=False) == 100


def test_audit_ranks_large_lockfile(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n" * 5, encoding="utf-8")
    # big lockfile
    (tmp_path / "package-lock.json").write_text("{" + ("\"a\":1," * 5000) + "}\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x" * 10000, encoding="utf-8")

    result = audit(tmp_path)
    assert result.files
    # node_modules skipped
    assert all("node_modules" not in f.path for f in result.files)
    # lockfile should dominate
    assert result.files[0].category == "lockfile"
    assert result.by_category["lockfile"]["tokens_est"] > result.by_category.get("source", {}).get("tokens_est", 0)


def test_suggest_includes_lockfile(tmp_path: Path):
    (tmp_path / "pnpm-lock.yaml").write_text("x\n" * 2000, encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    result = audit(tmp_path)
    sug = suggest_agentignore(result)
    assert any("pnpm-lock.yaml" in s for s in sug)


def test_cli_scan_json(tmp_path: Path, capsys):
    (tmp_path / "a.py").write_text("print('hello world')\n", encoding="utf-8")
    assert main(["scan", "-C", str(tmp_path), "--json"]) == 0
    out = capsys.readouterr().out
    assert "total_tokens_est" in out


def test_cli_suggest_write(tmp_path: Path):
    (tmp_path / "yarn.lock").write_text("a" * 5000, encoding="utf-8")
    assert main(["suggest-ignore", "-C", str(tmp_path), "--write", "--force"]) == 0
    text = (tmp_path / ".agentignore").read_text(encoding="utf-8")
    assert "yarn.lock" in text


def test_categorize_source(tmp_path: Path):
    p = tmp_path / "x.ts"
    p.write_text("const x = 1\n", encoding="utf-8")
    assert categorize(p, False) == "source"
