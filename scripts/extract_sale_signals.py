#!/usr/bin/env python3
"""Extract sale-related phrases from HTML/text without truncating multiword matches."""

from collections import Counter
import re
import sys
from typing import Iterable, List, Tuple

# Longer, concrete phrases must precede broad skin-noise words.
_PATTERN = re.compile(
    r"(?<![a-z])end[\s_-]*of[\s_-]*season[\s_-]*sale(?![a-z])"
    r"|시즌\s*오프|(?<![a-z])season[\s_-]*off(?![a-z])"
    r"|블랙[\s_-]*프라이데이|(?<![a-z])black[\s_-]*friday(?![a-z])"
    r"|(?<![a-z])final[\s_-]*sale(?![a-z])"
    r"|(?<![a-z])up\s*to\s*\d{1,3}\s*%|최대\s*\d{1,3}\s*%|~\s*\d{1,3}\s*%"
    r"|\d{1,3}\s*%\s*(?:할인|off(?![a-z])|오프)"
    r"|세일|할인|행사|(?<![a-z])sale(?![a-z])|쿠폰"
    r"|(?<![a-z])coupon(?![a-z])|(?<![a-z])clearance(?![a-z])"
    r"|(?<![a-z])outlet(?![a-z])|아웃렛",
    re.IGNORECASE,
)

_CONCRETE = re.compile(
    r"^(?:end[\s_-]*of[\s_-]*season[\s_-]*sale"
    r"|시즌\s*오프|season[\s_-]*off"
    r"|블랙[\s_-]*프라이데이|black[\s_-]*friday"
    r"|final[\s_-]*sale"
    r"|up\s*to\s*\d{1,3}\s*%|최대\s*\d{1,3}\s*%|~\s*\d{1,3}\s*%"
    r"|\d{1,3}\s*%\s*(?:할인|off|오프))$",
    re.IGNORECASE,
)


def _normalize_display(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _signal_key(display: str) -> str:
    folded = display.casefold()
    compact = re.sub(r"[\s_-]+", "", folded)
    # Separator/case variants are the same semantic campaign phrase.
    for phrase in (
        "seasonoff", "finalsale", "endofseasonsale", "blackfriday",
        "시즌오프", "블랙프라이데이",
    ):
        if compact == phrase:
            return phrase
    return compact if re.search(r"\d", compact) else folded


def extract_signals(text: str, concrete_only: bool = False) -> List[Tuple[str, int]]:
    """Return ``[(first_seen_phrase, count)]`` sorted by count then phrase.

    Matching is case-insensitive, so ``Up to 80%`` and ``UP TO 80%`` share a
    count. The first spelling is retained for readable output.
    """
    counts: Counter[str] = Counter()
    displays = {}
    for match in _PATTERN.finditer(text):
        display = _normalize_display(match.group(0))
        if concrete_only and not _CONCRETE.match(display):
            continue
        key = _signal_key(display)
        counts[key] += 1
        displays.setdefault(key, display)
    return [
        (displays[key], count)
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def format_signals(signals: Iterable[Tuple[str, int]]) -> str:
    return ",".join(f"{phrase}({count})" for phrase, count in signals)


def main() -> int:
    text = sys.stdin.read()
    print(format_signals(extract_signals(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
