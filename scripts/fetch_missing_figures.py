#!/usr/bin/env python3
"""Download the 11 missing PMC figures referenced by vision proposals.

Reads ``artifacts/vision_proposals_pipeline.jsonl``, identifies proposals
whose figure is not yet present at ``artifacts/figures/{figure_id}.jpg``,
and downloads them directly from PMC into that location.

Naming convention is the one ``scripts/run_vision_dual_smoke_qwen.py``
expects: ``{pmcid}_{fig_label}.{ext}``. The ``figure_id`` in the
proposals already follows this convention.

PMC layout note (2026): figures are served from the CDN
``cdn.ncbi.nlm.nih.gov/pmc/blobs/...`` rather than ``/pmc/articles/.../bin/``.
The article HTML at ``ncbi.nlm.nih.gov/pmc/articles/{PMCID}/`` lists CDN URLs;
we sweep the HTML for them and pick the one whose filename contains the
target ``fig_label`` substring (case-insensitive).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "artifacts" / "vision_proposals_pipeline.jsonl"
FIGURES_DIR = ROOT / "artifacts" / "figures"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

CDN_PATTERN = re.compile(
    r'src="(https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^"]+\.(?:jpg|jpeg|png|gif))"',
    re.IGNORECASE,
)
LABEL_HINT_PATTERN = re.compile(r"(Fig\d+|F\d+|f\d+|g\d+)", re.IGNORECASE)


def _http_get(url: str, timeout: int = 30) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {url}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def _fetch_article_html(pmcid: str) -> str | None:
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    raw = _http_get(url)
    if raw is None:
        return None
    return raw.decode("utf-8", errors="replace")


def _candidate_cdn_urls(html: str) -> list[str]:
    """Return CDN image URLs in document order, deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for url in CDN_PATTERN.findall(html):
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _match_fig_label(cdn_urls: list[str], fig_label: str) -> str | None:
    """Pick the CDN URL whose filename hint matches ``fig_label``.

    Strategy:
      1. Exact-substring match on filename stem.
      2. Match by extracted Fig/g/f/F-token (Fig5 ↔ "Fig5_HTML").
      3. Fall back to ordinal — ``g004`` → 4th figure if nothing else fits.
    """
    fig_lower = fig_label.lower()
    # Exact substring on filename
    for url in cdn_urls:
        fname = url.rsplit("/", 1)[-1].lower()
        if fig_lower in fname:
            return url
    # Token match
    target_token = LABEL_HINT_PATTERN.search(fig_label)
    if target_token:
        token = target_token.group(1).lower()
        for url in cdn_urls:
            fname = url.rsplit("/", 1)[-1].lower()
            tokens_in_fname = LABEL_HINT_PATTERN.findall(fname)
            for t in tokens_in_fname:
                if t.lower() == token:
                    return url
    # Ordinal fallback — pull a number off the fig_label and pick that index.
    ordinal_match = re.search(r"(\d+)", fig_label)
    if ordinal_match and cdn_urls:
        idx = int(ordinal_match.group(1)) - 1
        if 0 <= idx < len(cdn_urls):
            return cdn_urls[idx]
    return None


def _decompose(figure_id: str) -> tuple[str, str] | None:
    """``PMC10176953_Fig5`` → (``PMC10176953``, ``Fig5``)."""
    m = re.match(r"(PMC\d+)_(.+)", figure_id)
    if not m:
        return None
    return m.group(1), m.group(2)


def main() -> int:
    if not PROPOSALS.exists():
        print(f"ERROR: proposals not found: {PROPOSALS}", file=sys.stderr)
        return 1
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    proposals = [
        json.loads(line) for line in PROPOSALS.read_text().splitlines() if line.strip()
    ]
    targets: list[tuple[str, str]] = []  # (pmcid, fig_label)
    seen_figure_ids: set[str] = set()
    for p in proposals:
        figure_id = p.get("figure_id") or ""
        if not figure_id or figure_id in seen_figure_ids:
            continue
        # Skip if already present locally (any extension)
        already = any(
            (FIGURES_DIR / f"{figure_id}{ext}").exists()
            for ext in (".jpg", ".jpeg", ".png", ".webp")
        )
        if already:
            continue
        decomposed = _decompose(figure_id)
        if decomposed is None:
            print(f"  SKIP {figure_id}: cannot decompose into (PMCID, fig_label)",
                  file=sys.stderr)
            continue
        targets.append(decomposed)
        seen_figure_ids.add(figure_id)

    print(f"Found {len(targets)} missing figures to fetch")
    if not targets:
        return 0

    # Group by PMCID so we fetch each article HTML once.
    by_pmcid: dict[str, list[str]] = {}
    for pmcid, fig_label in targets:
        by_pmcid.setdefault(pmcid, []).append(fig_label)

    downloaded = 0
    failed: list[str] = []
    for pmcid, fig_labels in by_pmcid.items():
        print(f"\n[{pmcid}] fetching article HTML (figs requested: {fig_labels})")
        html = _fetch_article_html(pmcid)
        if html is None:
            for fl in fig_labels:
                failed.append(f"{pmcid}_{fl}")
            continue
        cdn_urls = _candidate_cdn_urls(html)
        if not cdn_urls:
            print(f"  WARN: no CDN figure URLs found in {pmcid} article HTML",
                  file=sys.stderr)
            for fl in fig_labels:
                failed.append(f"{pmcid}_{fl}")
            continue

        for fig_label in fig_labels:
            chosen = _match_fig_label(cdn_urls, fig_label)
            figure_id = f"{pmcid}_{fig_label}"
            if chosen is None:
                print(f"  MISS {figure_id}: no CDN URL matched fig_label",
                      file=sys.stderr)
                failed.append(figure_id)
                continue
            ext = chosen.rsplit(".", 1)[-1].lower()
            if ext not in {"jpg", "jpeg", "png", "webp"}:
                ext = "jpg"
            save_path = FIGURES_DIR / f"{figure_id}.{ext}"
            data = _http_get(chosen)
            if data is None or len(data) < 1024:
                failed.append(figure_id)
                continue
            save_path.write_bytes(data)
            print(f"  OK   {figure_id} → {save_path.name} ({len(data)} bytes)")
            downloaded += 1
            time.sleep(0.5)  # polite to PMC CDN
        time.sleep(1.0)

    print(f"\nDownloaded {downloaded} of {len(targets)} target figures.")
    if failed:
        print(f"Failed: {failed}")
        return 2 if downloaded == 0 else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
