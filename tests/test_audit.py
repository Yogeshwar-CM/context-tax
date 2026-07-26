from pathlib import Path

from context_tax.audit import (
    IgnoreMatcher,
    audit,
    categorize,
    estimate_tokens,
    parse_ignore_patterns,
    suggest_agentignore,
)
from context_tax.cli import main


def paths(result) -> set[str]:
    return {f.path for f in result.files}


def test_estimate_tokens_text():
    raw = b"abcd" * 100  # 400 chars -> ~100 tokens
    assert estimate_tokens(raw, is_binary=False) == 100


def test_estimate_tokens_binary_uses_bytes_over_two():
    assert estimate_tokens(b"\x00" * 100, is_binary=True) == 50


def test_estimate_tokens_never_zero():
    assert estimate_tokens(b"", is_binary=False) == 1


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


def test_categorize_docs_config_generated_binary(tmp_path: Path):
    assert categorize(tmp_path / "README.md", False) == "docs"
    assert categorize(tmp_path / "tsconfig.json", False) == "config"
    assert categorize(tmp_path / "app.min.js", False) == "generated"
    assert categorize(tmp_path / "logo.png", False) == "binary"


# --- .gitignore support -------------------------------------------------


def test_gitignore_respected_by_default(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s" * 400, encoding="utf-8")
    (tmp_path / "keep.py").write_text("print(1)\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "secret.txt" not in paths(result)
    assert "keep.py" in paths(result)
    assert result.ignored_by_rules == 1


def test_gitignore_can_be_disabled(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("secret.txt\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s" * 400, encoding="utf-8")

    result = audit(tmp_path, respect_gitignore=False)
    assert "secret.txt" in paths(result)
    assert result.ignored_by_rules == 0


def test_gitignore_directory_pattern_prunes_tree(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("out/\n", encoding="utf-8")
    (tmp_path / "out" / "deep").mkdir(parents=True)
    (tmp_path / "out" / "deep" / "blob.js").write_text("x" * 4000, encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")

    result = audit(tmp_path)
    assert all(not p.startswith("out") for p in paths(result))
    assert "app.py" in paths(result)


def test_gitignore_glob_and_negation(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n!keep.log\n", encoding="utf-8")
    (tmp_path / "drop.log").write_text("noise\n", encoding="utf-8")
    (tmp_path / "keep.log").write_text("signal\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "keep.log" in paths(result)
    assert "drop.log" not in paths(result)


def test_gitignore_anchored_pattern_only_matches_root(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("/build.py\n", encoding="utf-8")
    (tmp_path / "build.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "build.py").write_text("print(1)\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "build.py" not in paths(result)
    assert "pkg/build.py" in paths(result)


def test_nested_gitignore_is_scoped_to_its_directory(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / ".gitignore").write_text("data.json\n", encoding="utf-8")
    (tmp_path / "a" / "data.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "b" / "data.json").write_text("{}\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "a/data.json" not in paths(result)
    assert "b/data.json" in paths(result)


def test_agentignore_patterns_are_applied(tmp_path: Path):
    (tmp_path / ".agentignore").write_text("*.snap\n", encoding="utf-8")
    (tmp_path / "ui.snap").write_text("x" * 800, encoding="utf-8")
    (tmp_path / "ui.py").write_text("print(1)\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "ui.snap" not in paths(result)
    assert "ui.py" in paths(result)
    # ...and follow_ignores=False turns them off
    assert "ui.snap" in paths(audit(tmp_path, follow_ignores=False))


def test_double_star_pattern(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("docs/**/gen.md\n", encoding="utf-8")
    (tmp_path / "docs" / "x" / "y").mkdir(parents=True)
    (tmp_path / "docs" / "x" / "y" / "gen.md").write_text("g\n", encoding="utf-8")
    (tmp_path / "docs" / "keep.md").write_text("k\n", encoding="utf-8")

    result = audit(tmp_path)
    assert "docs/x/y/gen.md" not in paths(result)
    assert "docs/keep.md" in paths(result)


def test_parse_ignore_patterns_skips_comments_and_blanks():
    rules = parse_ignore_patterns("# comment\n\n  \n*.py\n")
    assert len(rules) == 1
    assert not rules[0].negated and not rules[0].dir_only


def test_ignore_matcher_last_match_wins():
    m = IgnoreMatcher()
    m.add("", parse_ignore_patterns("*.txt\n!notes.txt\n"))
    assert m.is_ignored("a.txt", is_dir=False)
    assert not m.is_ignored("notes.txt", is_dir=False)
    assert not m.is_ignored("a.py", is_dir=False)


def test_dir_only_rule_does_not_match_file():
    m = IgnoreMatcher()
    m.add("", parse_ignore_patterns("build/\n"))
    assert m.is_ignored("build", is_dir=True)
    assert not m.is_ignored("build", is_dir=False)


# --- CLI wiring ---------------------------------------------------------


def test_cli_no_respect_gitignore_flag(tmp_path: Path, capsys):
    (tmp_path / ".gitignore").write_text("big.txt\n", encoding="utf-8")
    (tmp_path / "big.txt").write_text("x" * 4000, encoding="utf-8")

    assert main(["scan", "-C", str(tmp_path), "--json"]) == 0
    assert "big.txt" not in capsys.readouterr().out

    assert main(["scan", "-C", str(tmp_path), "--json", "--no-respect-gitignore"]) == 0
    assert "big.txt" in capsys.readouterr().out


def test_cli_no_ignore_overrides_respect_gitignore(tmp_path: Path, capsys):
    (tmp_path / ".gitignore").write_text("big.txt\n", encoding="utf-8")
    (tmp_path / "big.txt").write_text("x" * 4000, encoding="utf-8")

    assert main(["scan", "-C", str(tmp_path), "--json", "--no-ignore"]) == 0
    out = capsys.readouterr().out
    assert "big.txt" in out
    assert '"ignored_by_rules": 0' in out


def test_cli_scan_human_output_mentions_ignored(tmp_path: Path, capsys):
    (tmp_path / ".gitignore").write_text("junk.txt\n", encoding="utf-8")
    (tmp_path / "junk.txt").write_text("x" * 400, encoding="utf-8")
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")

    assert main(["scan", "-C", str(tmp_path)]) == 0
    assert "excluded 1 paths" in capsys.readouterr().out


def test_cli_bad_directory_returns_2(tmp_path: Path):
    assert main(["scan", "-C", str(tmp_path / "nope")]) == 2
