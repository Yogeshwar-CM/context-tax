"""Repo walk + token heuristics for agent context cost."""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path


# Default dirs agents should rarely load wholesale
DEFAULT_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    "coverage",
    ".next",
    ".nuxt",
    ".turbo",
    ".output",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".cache",
    "htmlcov",
    "vendor",
    "Pods",
    ".idea",
    ".vscode",
    ".cursor",
    ".eggs",
}

LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "bun.lock",
    "uv.lock",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    "pdm.lock",
}

GENERATED_HINTS = (
    ".min.js",
    ".min.css",
    ".map",
    ".wasm",
    ".pb.go",
    "_generated.",
    ".generated.",
)

BINARY_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".bz2",
    ".xz",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
}


@dataclass
class FileStat:
    path: str
    bytes: int
    tokens_est: int
    category: str  # source | lockfile | generated | binary | docs | config | other
    ext: str


@dataclass
class AuditResult:
    root: str
    files: list[FileStat]
    total_bytes: int
    total_tokens_est: int
    by_category: dict[str, dict[str, int]]
    by_ext: dict[str, dict[str, int]]
    skipped_dirs_hit: dict[str, int]


def estimate_tokens(raw: bytes, is_binary: bool) -> int:
    """
    Fast tokenizer-free estimate.
    - text: ~chars/4 (common ballpark for English/code mix)
    - binary: bill as full-file if someone attached it (bytes/2) — still flagged separately
    """
    if is_binary:
        return max(1, len(raw) // 2)
    # decode sample for char count; full file if small
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            return max(1, len(raw) // 2)
    # strip huge runs of whitespace a bit
    n = len(text)
    return max(1, n // 4)


def categorize(path: Path, is_binary: bool) -> str:
    name = path.name
    if name in LOCKFILES:
        return "lockfile"
    if is_binary or path.suffix.lower() in BINARY_EXT:
        return "binary"
    low = name.lower()
    if any(h in low for h in GENERATED_HINTS) or path.suffix.lower() in {".map"}:
        return "generated"
    if path.suffix.lower() in {".md", ".rst", ".txt", ".adoc"}:
        return "docs"
    if path.suffix.lower() in {
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
        ".properties",
    } or name in {
        "Dockerfile",
        "Makefile",
        "Justfile",
        ".gitignore",
        ".dockerignore",
    }:
        return "config"
    if path.suffix.lower() in {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".cs",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".swift",
        ".scala",
        ".vue",
        ".svelte",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
    }:
        return "source"
    return "other"


def _is_probably_binary(path: Path, sample: bytes) -> bool:
    if path.suffix.lower() in BINARY_EXT:
        return True
    if b"\x00" in sample[:8000]:
        return True
    return False


def load_agentignore(root: Path) -> set[str]:
    """Return extra directory/file name patterns from .agentignore if present (simple)."""
    extra: set[str] = set()
    for fname in (".agentignore", ".gitignore"):
        p = root / fname
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("!"):
                    continue
                if line.startswith("#"):
                    continue
                # only simple single-segment dir names for skip set
                cleaned = line.strip("/")
                if "/" not in cleaned and "*" not in cleaned and cleaned:
                    extra.add(cleaned)
        except OSError:
            pass
    return extra


def audit(
    root: Path,
    *,
    max_file_bytes: int = 5_000_000,
    follow_ignores: bool = True,
    include_skipped_inventory: bool = True,
) -> AuditResult:
    root = root.resolve()
    skip_dirs = set(DEFAULT_SKIP_DIRS)
    if follow_ignores:
        skip_dirs |= load_agentignore(root)

    files: list[FileStat] = []
    skipped_dirs_hit: dict[str, int] = {}
    total_bytes = 0
    total_tokens = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # prune
        pruned = []
        keep = []
        for d in dirnames:
            if (
                d in skip_dirs
                or d.startswith(".git")
                or d.endswith(".egg-info")
                or d.endswith(".dist-info")
            ):
                pruned.append(d)
                if include_skipped_inventory:
                    # rough count of entries inside would be expensive; count dir hit
                    skipped_dirs_hit[d] = skipped_dirs_hit.get(d, 0) + 1
            else:
                keep.append(d)
        dirnames[:] = keep

        base = Path(dirpath)
        for name in filenames:
            path = base / name
            try:
                st = path.stat()
            except OSError:
                continue
            size = int(st.st_size)
            if size > max_file_bytes:
                # still record as huge binary-ish
                cat = "binary"
                tok = size // 2
                rel = str(path.relative_to(root))
                files.append(
                    FileStat(
                        path=rel,
                        bytes=size,
                        tokens_est=tok,
                        category=cat,
                        ext=path.suffix.lower() or name,
                    )
                )
                total_bytes += size
                total_tokens += tok
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            is_bin = _is_probably_binary(path, raw)
            cat = categorize(path, is_bin)
            tok = estimate_tokens(raw, is_bin)
            rel = str(path.relative_to(root))
            files.append(
                FileStat(
                    path=rel,
                    bytes=size,
                    tokens_est=tok,
                    category=cat,
                    ext=path.suffix.lower() or name,
                )
            )
            total_bytes += size
            total_tokens += tok

    files.sort(key=lambda f: f.tokens_est, reverse=True)

    by_cat: dict[str, dict[str, int]] = {}
    by_ext: dict[str, dict[str, int]] = {}
    for f in files:
        c = by_cat.setdefault(f.category, {"files": 0, "bytes": 0, "tokens_est": 0})
        c["files"] += 1
        c["bytes"] += f.bytes
        c["tokens_est"] += f.tokens_est
        e = by_ext.setdefault(f.ext or "(none)", {"files": 0, "bytes": 0, "tokens_est": 0})
        e["files"] += 1
        e["bytes"] += f.bytes
        e["tokens_est"] += f.tokens_est

    return AuditResult(
        root=str(root),
        files=files,
        total_bytes=total_bytes,
        total_tokens_est=total_tokens,
        by_category=by_cat,
        by_ext=by_ext,
        skipped_dirs_hit=skipped_dirs_hit,
    )


def suggest_agentignore(result: AuditResult, top_n: int = 30) -> list[str]:
    """Heuristic suggestions beyond defaults."""
    suggestions: list[str] = []
    # lockfiles
    locks = [f for f in result.files if f.category == "lockfile"]
    if locks:
        suggestions.append("# Lockfiles (huge, low signal for agents)")
        for f in locks[:20]:
            suggestions.append(f.path)

    # big generated / binary
    big = [
        f
        for f in result.files
        if f.category in {"generated", "binary"} and f.tokens_est >= 2_000
    ]
    if big:
        suggestions.append("# Large generated / binary")
        for f in big[: top_n]:
            suggestions.append(f.path)

    # huge docs dumps
    docs = [f for f in result.files if f.category == "docs" and f.tokens_est >= 8_000]
    if docs:
        suggestions.append("# Very large docs (consider summarizing or nesting)")
        for f in docs[:15]:
            suggestions.append(f.path)

    # heavy other
    other = [f for f in result.files if f.category == "other" and f.tokens_est >= 5_000]
    if other:
        suggestions.append("# Other large files")
        for f in other[:15]:
            suggestions.append(f.path)

    return suggestions


def cost_usd(tokens: int, usd_per_mtok: float) -> float:
    return (tokens / 1_000_000.0) * usd_per_mtok


def result_to_dict(result: AuditResult) -> dict:
    return {
        "root": result.root,
        "total_bytes": result.total_bytes,
        "total_tokens_est": result.total_tokens_est,
        "by_category": result.by_category,
        "by_ext": dict(
            sorted(result.by_ext.items(), key=lambda kv: -kv[1]["tokens_est"])[:40]
        ),
        "skipped_dirs_hit": result.skipped_dirs_hit,
        "top_files": [asdict(f) for f in result.files[:100]],
    }
