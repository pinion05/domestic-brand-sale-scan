#!/usr/bin/env python3
"""Render candidate stores with agent-browser and summarize visible sale signals."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
from typing import List
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from extract_sale_signals import extract_signals, format_signals  # noqa: E402


@dataclass(frozen=True)
class RenderTarget:
    code: str
    brand: str
    url: str
    key: str


def _safe(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "target"


def load_targets(path: Path) -> List[RenderTarget]:
    """Load either ``code/brand/url`` or ``code/domain/status/hits`` TSV."""
    targets = []
    key_counts = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        fields = line.split("\t")
        if len(fields) < 2 or fields[1] == "-":
            continue
        code = fields[0].strip()
        if len(fields) >= 3 and fields[2].startswith(("http://", "https://")):
            brand, url = fields[1].strip(), fields[2].strip()
        else:
            brand, url = "", fields[1].strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
        host = urlparse(url).hostname or "unknown"
        base_key = f"{_safe(code)}__{_safe(host)}"
        key_counts[base_key] = key_counts.get(base_key, 0) + 1
        suffix = "" if key_counts[base_key] == 1 else f"-{key_counts[base_key]}"
        targets.append(RenderTarget(code, brand, url, f"{base_key}{suffix}"))
    return targets


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _command(args: list, timeout: int, errors: list) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        if result.stderr.strip():
            errors.append(f"$ {' '.join(args)}\n{result.stderr.strip()}")
        return result
    except subprocess.TimeoutExpired as error:
        errors.append(f"$ {' '.join(args)}\nTIMEOUT after {timeout}s")
        return subprocess.CompletedProcess(
            args,
            124,
            _as_text(error.stdout),
            _as_text(error.stderr),
        )
    except OSError as error:
        errors.append(f"$ {' '.join(args)}\n{error}")
        return subprocess.CompletedProcess(args, 127, "", str(error))


def _stale_sale_years(text: str, current_year: int) -> List[int]:
    years = set()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    footer_marker = re.compile(
        r"business|license|mall-order|online order|copyright|address|사업자|통신판매|©",
        re.IGNORECASE,
    )
    for index, line in enumerate(lines):
        if not extract_signals(line, concrete_only=True):
            continue
        # Accessibility text may split one banner across a few adjacent lines.
        context_lines = lines[max(0, index - 2): index + 3]
        context_years = {
            int(raw_year)
            for candidate in context_lines
            if not footer_marker.search(candidate)
            for raw_year in re.findall(r"\b20\d{2}\b", candidate)
        }
        # A current campaign year outranks unrelated older metadata nearby.
        if current_year in context_years:
            continue
        years.update(year for year in context_years if year < current_year)
    return sorted(years)


def _summarize_visible_text(text: str, current_year: int) -> tuple:
    concrete = extract_signals(text, concrete_only=True)
    if not concrete:
        visible_sale_count = sum(
            count for phrase, count in extract_signals(text) if phrase.casefold() == "세일"
        )
        if visible_sale_count >= 15:
            concrete = [("세일", visible_sale_count)]
    signals = format_signals(concrete)
    stale_years = _stale_sale_years(text, current_year)
    if not text.strip():
        status = "render-failed"
    elif stale_years:
        status = "stale-year:" + ",".join(map(str, stale_years))
    elif signals:
        status = "visible-candidate"
    else:
        status = "no-concrete-visible-signal"
    return status, signals or "-"


def render_one(target: RenderTarget, outdir: Path, wait_ms: int, current_year: int) -> dict:
    errors = []
    session = f"sale-{target.key}"[:80]
    prefix = ["agent-browser", "--session", session]
    try:
        # open can time out after navigation while leaving a usable live page. Continue.
        _command(prefix + ["open", target.url], 60, errors)
        _command(prefix + ["wait", "--load", "networkidle"], 45, errors)
        _command(prefix + ["wait", str(wait_ms)], 20, errors)
        final_url = _command(prefix + ["get", "url"], 20, errors).stdout.strip()
        title = _command(prefix + ["get", "title"], 20, errors).stdout.strip()
        text = _command(prefix + ["get", "text", "body"], 30, errors).stdout
    finally:
        _command(prefix + ["close"], 20, errors)

    (outdir / f"{target.key}.url").write_text(final_url, encoding="utf-8")
    (outdir / f"{target.key}.title").write_text(title, encoding="utf-8")
    (outdir / f"{target.key}.txt").write_text(text, encoding="utf-8")
    (outdir / f"{target.key}.err").write_text("\n\n".join(errors), encoding="utf-8")

    status, signals = _summarize_visible_text(text, current_year)
    return {
        "code": target.code,
        "brand": target.brand,
        "url": target.url,
        "final_url": final_url,
        "status": status,
        "signals": signals,
        "artifact": str(outdir / f"{target.key}.txt"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path, help="candidate TSV")
    parser.add_argument("outdir", type=Path, help="render artifacts directory")
    parser.add_argument("--jobs", type=int, default=5)
    parser.add_argument("--wait-ms", type=int, default=2500)
    parser.add_argument("--current-year", type=int, default=datetime.now().year)
    args = parser.parse_args(argv)

    targets = load_targets(args.targets)
    args.outdir.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(render_one, target, args.outdir, args.wait_ms, args.current_year): target
            for target in targets
        }
        for future in as_completed(futures):
            results.append(future.result())

    order = {target.key: index for index, target in enumerate(targets)}
    # Artifact basename contains the unique key, preserving input order deterministically.
    results.sort(key=lambda row: order[Path(row["artifact"]).stem])
    summary = args.outdir / "summary.tsv"
    with summary.open("w", encoding="utf-8") as handle:
        handle.write("code\tbrand\tinput_url\tfinal_url\tstatus\tsignals\tartifact\n")
        for row in results:
            handle.write("\t".join(str(row[key]).replace("\t", " ") for key in (
                "code", "brand", "url", "final_url", "status", "signals", "artifact"
            )) + "\n")

    counts = {}
    for row in results:
        counts[row["status"].split(":", 1)[0]] = counts.get(row["status"].split(":", 1)[0], 0) + 1
    print(f"{len(results)} rendered -> {summary}")
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
