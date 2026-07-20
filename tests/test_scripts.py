#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ExtractSaleSignalsTest(unittest.TestCase):
    def test_preserves_multiword_signals_and_merges_case_variants(self):
        script = SCRIPTS / "extract_sale_signals.py"
        body = "SEASON OFF | Up to 80% | up TO 80% | FINAL SALE | 20% OFF | Coupon"
        result = subprocess.run(
            [sys.executable, str(script)],
            input=body,
            text=True,
            capture_output=True,
            check=True,
        )
        output = result.stdout.strip().upper()
        self.assertIn("UP TO 80%(2)", output)
        self.assertIn("SEASON OFF(1)", output)
        self.assertIn("FINAL SALE(1)", output)
        self.assertIn("20% OFF(1)", output)
        self.assertNotRegex(output, r"(?:^|,)UP\(\d+\)")
        self.assertNotRegex(output, r"(?:^|,)FINAL\(\d+\)")

    def test_treats_tilde_maximum_as_concrete_without_accepting_bare_percent(self):
        module = load_module("extract_sale_signals")
        text = "SUMMER FESTA ~90% | ordinary product 40% | coupon"
        concrete = module.extract_signals(text, concrete_only=True)
        self.assertEqual([("~90%", 1)], concrete)

    def test_merges_separator_variants_of_the_same_campaign_phrase(self):
        module = load_module("extract_sale_signals")
        signals = module.extract_signals("SEASON OFF | season-off | seasonoff")
        self.assertEqual([("SEASON OFF", 3)], signals)

    def test_english_markers_do_not_match_inside_longer_words(self):
        module = load_module("extract_sale_signals")
        noise = "season offering | preseason-offering | final sales | wholesale | 20% offer"
        self.assertEqual([], module.extract_signals(noise, concrete_only=True))
        valid = "SEASON-OFF | FINAL SALE | 20% OFF"
        self.assertEqual(3, len(module.extract_signals(valid, concrete_only=True)))


class ParseBrandsTest(unittest.TestCase):
    def test_output_is_a_domestic_fashion_candidate_set(self):
        fixture = {
            "data": {
                "modules": [
                    {
                        "items": [
                            {
                                "info": {
                                    "brandName": name,
                                    "onClickBrandName": {"url": f"/brand/{code}"},
                                }
                            }
                            for code, name in [
                                ("matinkim", "마뗑킴"),
                                ("blackyak", "블랙야크"),
                                ("boss", "보스"),
                                ("camper", "캠퍼"),
                                ("ellesse", "엘레쎄"),
                                ("beautyofjoseon", "조선미녀"),
                            ]
                        ]
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "parse_brands.py"), str(path)],
                text=True,
                capture_output=True,
                check=True,
            )
        codes = {line.split("\t", 1)[0] for line in result.stdout.splitlines()}
        self.assertEqual({"matinkim", "blackyak"}, codes)

    def test_overlapping_input_patterns_do_not_inflate_frequency(self):
        fixture = {
            "data": {"modules": [{"items": [{"info": {
                "brandName": "마뗑킴",
                "onClickBrandName": {"url": "/brand/matinkim"},
            }}]}]}
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "page.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "parse_brands.py"), str(path), str(path)],
                text=True,
                capture_output=True,
                check=True,
            )
        self.assertEqual("matinkim\t마뗑킴\t1", result.stdout.strip())


class MapMissesTest(unittest.TestCase):
    def test_filters_marketplaces_social_and_unrelated_results(self):
        module = load_module("map_misses")
        results = [
            {"url": "https://www.musinsa.com/brand/drawfit", "title": "무신사"},
            {"url": "https://shop.29cm.co.kr/brand/16175", "title": "29CM"},
            {"url": "https://www.instagram.com/drawfit_official", "title": "Instagram"},
            {"url": "https://draw-fit.com/", "title": "드로우핏 공식몰"},
        ]
        candidates = module.filter_candidates(results)
        self.assertEqual(["https://draw-fit.com/"], [x["url"] for x in candidates])

    def test_rejected_http_candidate_can_be_forced_back_into_search(self):
        module = load_module("map_misses")
        brands = [("cornell", "캔버스"), ("untapped", "언탭트 스튜디오")]
        targets = module.select_search_targets(
            brands,
            mapped_codes={"cornell"},
            forced_codes={"cornell"},
        )
        self.assertEqual(brands, targets)

    def test_transient_search_failure_does_not_poison_cache(self):
        module = load_module("map_misses")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            brands = root / "brands.tsv"
            scan = root / "scan.tsv"
            cache = root / "cache.json"
            brands.write_text("drawfit\t드로우핏\t1\n", encoding="utf-8")
            scan.write_text("drawfit\t-\t-\t-\n", encoding="utf-8")
            module.brave_search = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("transient"))
            previous_key = os.environ.get("BRAVE_API_KEY")
            os.environ["BRAVE_API_KEY"] = "test"
            try:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    self.assertEqual(0, module.main([str(brands), str(scan), "--cache", str(cache)]))
            finally:
                if previous_key is None:
                    os.environ.pop("BRAVE_API_KEY", None)
                else:
                    os.environ["BRAVE_API_KEY"] = previous_key
            payload = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        self.assertNotIn("drawfit", payload)


class RenderTargetParsingTest(unittest.TestCase):
    def test_tsv_parsing_preserves_spaced_brand_names_and_duplicate_codes(self):
        module = load_module("render_verify")
        rows = "\n".join(
            [
                "untapped\t언탭트 스튜디오\thttps://untappedstudio.co.kr/",
                "matinkim\tmatinkim.co.kr\t200\tSEASON OFF(1)",
                "matinkim\tmatinkim.com\t200\tUP TO 80%(1)",
                "missing\t-\t-\t-",
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "targets.tsv"
            path.write_text(rows, encoding="utf-8")
            targets = module.load_targets(path)
        self.assertEqual(
            [
                ("untapped", "언탭트 스튜디오", "https://untappedstudio.co.kr/"),
                ("matinkim", "", "https://matinkim.co.kr"),
                ("matinkim", "", "https://matinkim.com"),
            ],
            [(x.code, x.brand, x.url) for x in targets],
        )
        self.assertEqual(len(targets), len({x.key for x in targets}))


class RenderCommandTest(unittest.TestCase):
    def test_timeout_result_remains_text_when_partial_stdout_was_captured(self):
        module = load_module("render_verify")
        errors = []
        result = module._command(
            ["bash", "-c", "printf partial; sleep 1"],
            timeout=0.05,
            errors=errors,
        )
        self.assertIsInstance(result.stdout, str)
        self.assertEqual("partial", result.stdout)
        self.assertTrue(errors)

    def test_stale_year_guard_handles_dom_line_breaks(self):
        module = load_module("render_verify")
        text = "2025\nFLAT PRICE SALE\nUP TO 87% OFF"
        self.assertEqual([2025], module._stale_sale_years(text, current_year=2026))

    def test_stale_year_guard_ignores_sale_substrings_inside_words(self):
        module = load_module("render_verify")
        text = "2025 wholesale catalog\nCurrent collection"
        self.assertEqual([], module._stale_sale_years(text, current_year=2026))

    def test_visible_korean_sale_threshold_matches_documented_rule(self):
        module = load_module("render_verify")
        status_14, _ = module._summarize_visible_text("세일\n" * 14, current_year=2026)
        status_15, signals_15 = module._summarize_visible_text("세일\n" * 15, current_year=2026)
        self.assertEqual("no-concrete-visible-signal", status_14)
        self.assertEqual("visible-candidate", status_15)
        self.assertEqual("세일(15)", signals_15)


class ScanScriptTest(unittest.TestCase):
    def test_all_mode_probes_every_slug_domain_and_keeps_full_phrases(self):
        with tempfile.TemporaryDirectory() as td:
            fake_curl = Path(td) / "curl"
            fake_curl.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    case " $* " in
                      *" -I "*) printf '405'; exit 0 ;;
                    esac
                    out=''
                    previous=''
                    for argument in "$@"; do
                      if [ "$previous" = '-o' ]; then out="$argument"; fi
                      previous="$argument"
                    done
                    [ -n "$out" ] && printf 'SEASON OFF Up to 80%% FINAL SALE' > "$out"
                    printf '200'
                    """
                ),
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{td}:{env['PATH']}"
            result = subprocess.run(
                ["bash", str(SCRIPTS / "scan.sh"), "--all", "samplebrand"],
                text=True,
                capture_output=True,
                env=env,
                check=True,
            )
        lines = result.stdout.splitlines()
        self.assertEqual(3, len(lines))
        self.assertEqual(
            ["samplebrand.co.kr", "samplebrand.kr", "samplebrand.com"],
            [line.split("\t")[1] for line in lines],
        )
        for line in lines:
            upper = line.upper()
            self.assertIn("UP TO 80%(1)", upper)
            self.assertIn("FINAL SALE(1)", upper)


if __name__ == "__main__":
    unittest.main(verbosity=2)
