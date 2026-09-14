#!/usr/bin/env python3
"""Merge render artifacts from multiple retry passes into one summary.

Newest pass wins for a target's artifacts: rendered4 > rendered3 > rendered2 > rendered.
Statuses are re-derived with render_verify._summarize_visible_text for consistency.
Manual overrides: rendered/manual-*.txt (brand resolved from render-input.tsv url).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_verify import _summarize_visible_text, load_targets

ROOT = Path(__file__).parent.parent
PASSES = [ROOT / "rendered4", ROOT / "rendered3", ROOT / "rendered2", ROOT / "rendered"]

MANUAL = {
    "https://www.stco.co.kr/": ROOT / "rendered" / "manual-stco.txt",
}


def main() -> int:
    targets = load_targets(ROOT / "render-input.tsv")
    rows = []
    for t in targets:
        text = ""
        artifact = ""
        for p in PASSES:
            f = p / f"{t.key}.txt"
            if f.exists() and f.stat().st_size > 0:
                text = f.read_text(encoding="utf-8")
                artifact = str(f)
                break
        if t.url in MANUAL and MANUAL[t.url].exists():
            text = MANUAL[t.url].read_text(encoding="utf-8")
            artifact = str(MANUAL[t.url])
        status, signals = _summarize_visible_text(text, 2026)
        rows.append({
            "code": t.code, "brand": t.brand, "url": t.url,
            "final_url": "", "status": status, "signals": signals, "artifact": artifact,
        })
    out = ROOT / "merged-summary.tsv"
    with out.open("w", encoding="utf-8") as h:
        h.write("code\tbrand\turl\tfinal_url\tstatus\tsignals\tartifact\n")
        for r in rows:
            h.write("\t".join(str(r[k]) for k in
                     ("code", "brand", "url", "final_url", "status", "signals", "artifact")) + "\n")
    from collections import Counter
    print(Counter(r["status"] for r in rows))
    print(f"{len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
