#!/usr/bin/env python3
"""Download figure images and captions from PMC for all papers with a PMCID.

Reads papers from PAPERS_FILE, fetches the PMC HTML for each paper that has a
PMCID, extracts (figure_id, image_url, caption) tuples, downloads images to
SAMPLE_DIR/<pmcid_lower>_figures/, and writes a figures JSONL consumed by
index_figures.py and propose_vision_qwen.py.

Usage:
    conda run -n base python scripts/fetch_pmc_figures.py [--papers FILE] [--output FILE]
"""
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SAMPLE_DIR = "/Users/junlee/Desktop/sanomap-radiomics-layer/sample_papers"
PAPERS_FILE = "/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/papers_microbe_merged_fulltext.jsonl"
DEFAULT_OUTPUT = "/Users/junlee/Desktop/sanomap-radiomics-layer/artifacts/figures_pmc.jsonl"

HEATMAP_CAPTION_KEYWORDS = {
    "heatmap", "heat map", "correlation matrix", "cluster map",
    "clustermap", "spearman", "pearson", "colormap", "color map",
    "correlation heatmap",
}


def _caption_suggests_heatmap(caption: str) -> bool:
    lower = caption.lower()
    return any(kw in lower for kw in HEATMAP_CAPTION_KEYWORDS)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


# ---------------------------------------------------------------------------
# HTML caption + image extraction
# ---------------------------------------------------------------------------

class _FigureParser(HTMLParser):
    """Extract (figure_label, caption_text, [img_src, ...]) from PMC article HTML.

    PMC uses two common structures:
      1. <div class="fig" id="fig1">
           <div class="caption"><p>Figure 1. Caption...</p></div>
           <div class="graphic"><img src="/pmc/.../figX.jpg"></div>
         </div>
      2. <figure id="F1">
           <figcaption><p>Figure 1. Caption...</p></figcaption>
           <img src="/pmc/.../figX.jpg">
         </figure>
    """

    def __init__(self) -> None:
        super().__init__()
        self.figures: list[dict] = []
        self._in_fig = False
        self._in_caption = False
        self._fig_depth = 0
        self._caption_buf: list[str] = []
        self._current_imgs: list[str] = []
        self._current_id = ""
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        self._depth += 1

        # Detect figure container
        is_fig_div = tag == "div" and ("fig" in (attr.get("class") or "") or "figure" in (attr.get("class") or ""))
        is_figure_tag = tag == "figure"
        if is_fig_div or is_figure_tag:
            if not self._in_fig:
                self._in_fig = True
                self._fig_depth = self._depth
                self._current_id = attr.get("id") or ""
                self._caption_buf = []
                self._current_imgs = []
            return

        if self._in_fig:
            # Detect caption container
            is_caption = (
                (tag == "div" and "caption" in (attr.get("class") or ""))
                or tag == "figcaption"
                or (tag == "p" and "caption" in (attr.get("class") or ""))
            )
            if is_caption:
                self._in_caption = True

            # Collect image src
            if tag == "img":
                src = attr.get("src") or attr.get("data-src") or ""
                if src:
                    self._current_imgs.append(src)

    def handle_endtag(self, tag: str) -> None:
        if self._in_fig and self._depth == self._fig_depth and tag in {"div", "figure"}:
            caption = " ".join(self._caption_buf).strip()
            # re-collapse whitespace
            caption = re.sub(r"\s+", " ", caption)
            self.figures.append({
                "fig_id": self._current_id,
                "caption": caption,
                "img_srcs": list(self._current_imgs),
            })
            self._in_fig = False
            self._in_caption = False
            self._caption_buf = []
            self._current_imgs = []
        elif self._in_caption and tag in {"div", "figcaption", "p"}:
            self._in_caption = False
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_caption:
            self._caption_buf.append(data)


def _extract_figures_from_html(html: str, pmcid: str) -> list[dict]:
    """Return list of dicts: {fig_id, caption, img_srcs}."""
    parser = _FigureParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    # Fallback: regex sweep for any figure-like img src not caught by the parser
    if not parser.figures:
        pmcid_num = pmcid.replace("PMC", "")
        patterns = [
            rf'src="(/pmc/articles/{pmcid}/bin/[^"]+\.(?:jpg|png|gif))"',
            rf'src="([^"]*{pmcid_num}[^"]*\.(?:jpg|png|gif))"',
        ]
        srcs: set[str] = set()
        for pat in patterns:
            for m in re.findall(pat, html, re.IGNORECASE):
                srcs.add(m)
        if srcs:
            return [{"fig_id": f"fig_{i}", "caption": "", "img_srcs": [s]} for i, s in enumerate(sorted(srcs))]

    return parser.figures


def _absolute_url(src: str) -> str:
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return f"https://www.ncbi.nlm.nih.gov{src}"
    return src


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return ""


def _download_file(url: str, save_path: str) -> int:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        with open(save_path, "wb") as f:
            f.write(data)
        return len(data)
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}")
        return 0


# ---------------------------------------------------------------------------
# Per-paper processing
# ---------------------------------------------------------------------------

def process_pmcid(pmcid: str, pmid: str, fig_base_dir: str) -> list[dict]:
    """Fetch all figures + captions for one PMCID. Returns list of figure dicts."""
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    html = _fetch_html(url)
    if not html:
        return []

    raw_figures = _extract_figures_from_html(html, pmcid)
    fig_dir = os.path.join(fig_base_dir, f"{pmcid.lower()}_figures")
    os.makedirs(fig_dir, exist_ok=True)

    results: list[dict] = []
    for fig in raw_figures:
        fig_id = fig["fig_id"] or f"fig_{len(results)}"
        caption = fig["caption"]
        downloaded_path: str | None = None

        for src in fig["img_srcs"]:
            ext = os.path.splitext(src.split("?")[0])[-1].lower() or ".jpg"
            if ext not in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"}:
                ext = ".jpg"
            fname = f"{fig_id}{ext}" if fig_id else f"fig_{len(results)}{ext}"
            save_path = os.path.join(fig_dir, fname)

            if os.path.exists(save_path):
                downloaded_path = os.path.abspath(save_path)
                break

            abs_url = _absolute_url(src)
            size = _download_file(abs_url, save_path)
            time.sleep(0.4)
            if size > 0:
                downloaded_path = os.path.abspath(save_path)
                print(f"  {pmcid}/{fig_id}: {fname} ({size} bytes)  caption={caption[:60]!r}")
                break

        results.append({
            "figure_id": f"{pmcid}_{fig_id}",
            "pmid": pmid,
            "pmcid": pmcid,
            "fig_label": fig_id,
            "caption": caption,
            "image_path": downloaded_path,
        })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", default=PAPERS_FILE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-dir", default=SAMPLE_DIR)
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process (0 = all)")
    parser.add_argument(
        "--heatmap-only",
        action="store_true",
        help="Only write figures whose caption contains heatmap-related keywords.",
    )
    parser.add_argument(
        "--pmcids",
        default="",
        help="Comma-separated list of specific PMCIDs to process (overrides --papers).",
    )
    args = parser.parse_args()

    # Build target list: explicit --pmcids flag overrides --papers
    if args.pmcids.strip():
        explicit = [p.strip() for p in args.pmcids.split(",") if p.strip()]
        targets = [(pmcid, "") for pmcid in explicit]
    else:
        papers_path = Path(args.papers)
        if not papers_path.exists():
            print(f"Papers file not found: {papers_path}")
            sys.exit(1)

        with open(papers_path) as f:
            papers = [json.loads(line) for line in f if line.strip()]

        # Deduplicate PMCIDs — one run per article
        seen_pmcids: set[str] = set()
        targets = []  # (pmcid, pmid)
        for p in papers:
            pmcid = (p.get("pmcid") or "").strip()
            pmid = str(p.get("pmid") or "")
            if pmcid and pmcid not in seen_pmcids:
                seen_pmcids.add(pmcid)
                targets.append((pmcid, pmid))

    if args.limit > 0:
        targets = targets[: args.limit]

    print(f"Processing {len(targets)} unique PMCIDs")

    all_figures: list[dict] = []
    for i, (pmcid, pmid) in enumerate(targets):
        print(f"\n[{i+1}/{len(targets)}] {pmcid} (PMID {pmid})")
        figs = process_pmcid(pmcid, pmid, args.sample_dir)
        all_figures.extend(figs)
        time.sleep(1.0)  # polite inter-paper delay

    if args.heatmap_only:
        before = len(all_figures)
        all_figures = [f for f in all_figures if _caption_suggests_heatmap(f.get("caption") or "")]
        print(f"\n--heatmap-only: {before} → {len(all_figures)} figures (caption filter applied)")

    with open(args.output, "w") as f:
        for fig in all_figures:
            f.write(json.dumps(fig) + "\n")

    with_image = sum(1 for fig in all_figures if fig.get("image_path"))
    with_caption = sum(1 for fig in all_figures if fig.get("caption"))
    print(f"\nDone. {len(all_figures)} figures — {with_image} with image, {with_caption} with caption")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
