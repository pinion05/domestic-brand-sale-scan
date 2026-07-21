#!/usr/bin/env python3
"""
Merge today's Musinsa ranking into the cumulative brand-urls.json registry.

Workflow:
  1. fetch_all_brands.sh → brands.tsv (today's fresh ranking, Korean brand names)
  2. THIS SCRIPT: merge brands.tsv names into data/brand-urls.json
     - name already in registry → skip probe (URL already known)
     - name NOT in registry → output to TSV for Phase 2 slug probing
  3. Phase 2-5 scan only the NEW brands; registry brands go straight to render

Usage:
  python3 scripts/merge_registry.py brands.tsv data/brand-urls.json \
    > new-brands.tsv

After Phase 2-5 verifies a new brand's URL, add it to brand-urls.json:
  python3 scripts/merge_registry.py --add-new new-verified.tsv data/brand-urls.json
"""
import argparse
import json
import sys
from pathlib import Path


def load_registry(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_today_brands(path: Path) -> list[tuple[str, str]]:
    """Return [(code, korean_name), ...] from brands.tsv."""
    brands = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            brands.append((fields[0], fields[1]))
    return brands


def cmd_filter(args):
    """Split brands.tsv into known (skip) vs new (probe)."""
    registry = load_registry(args.registry)
    today = load_today_brands(args.brands)

    known, new_codes = [], []
    for code, name in today:
        if name in registry:
            known.append((code, name, registry[name]))
        else:
            new_codes.append((code, name))

    # Output new brands as TSV for Phase 2 slug probing
    for code, name in new_codes:
        print(f"{code}\t{name}")

    # Summary to stderr
    print(
        f"registry: {len(registry)} brands | "
        f"today: {len(today)} | "
        f"known (skip probe): {len(known)} | "
        f"new (probe needed): {len(new_codes)}",
        file=sys.stderr,
    )


def cmd_add_new(args):
    """Add newly verified brands (from render summary) to registry.

    Input TSV: code<TAB>brand<TAB>url  (from render summary visible-candidate rows)
    Only adds brands whose url is non-empty and not '-'.
    """
    registry = load_registry(args.registry)
    added = 0
    for line in args.input.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        code, brand, url = fields[0], fields[1], fields[2]
        if brand in registry:
            continue
        if not url or url == "-":
            continue
        registry[brand] = url
        added += 1

    # Sort registry by brand name
    registry = dict(sorted(registry.items()))
    args.registry.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"added {added} new brands → {args.registry} ({len(registry)} total)",
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brands", type=Path, nargs="?", help="brands.tsv")
    parser.add_argument("registry", type=Path, help="data/brand-urls.json")
    parser.add_argument(
        "--add-new",
        action="store_true",
        help="Add newly verified brands from TSV input to registry",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input TSV for --add-new (code<TAB>brand<TAB>url)",
    )
    args = parser.parse_args()

    if args.add_new:
        if not args.input:
            parser.error("--add-new requires --input TSV file")
        cmd_add_new(args)
    else:
        if not args.brands:
            parser.error("brands.tsv path required")
        cmd_filter(args)


if __name__ == "__main__":
    main()
