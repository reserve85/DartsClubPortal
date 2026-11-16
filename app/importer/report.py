"""Import report shared by the Elo and penalty importers (CLI + admin page)."""

from dataclasses import dataclass, field


class ImportAborted(Exception):
    """The import cannot run (wrong file, data already present, ...)."""


@dataclass
class ImportReport:
    kind: str
    dry_run: bool
    counts: dict = field(default_factory=dict)
    matched: list = field(default_factory=list)  # (what, source name, portal name)
    created: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    checks: list = field(default_factory=list)  # (label, ok: bool, detail)

    def add(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    @property
    def ok(self) -> bool:
        return all(ok for _label, ok, _detail in self.checks)

    def as_text(self) -> str:
        lines = [f"{self.kind} import{' (preview, nothing saved)' if self.dry_run else ''}"]
        lines += [f"  {k}: {v}" for k, v in sorted(self.counts.items())]
        if self.matched:
            lines.append("  matched:")
            lines += [f"    {w}: {a} -> {b}" for w, a, b in self.matched]
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        for label, ok, detail in self.checks:
            lines.append(f"  [{'OK' if ok else 'FAIL'}] {label}: {detail}")
        return "\n".join(lines)
