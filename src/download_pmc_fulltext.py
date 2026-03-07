from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import ensure_parent, read_jsonl, write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import PaperRecord, from_dict, to_dict

PMC_ARTICLE_URL = "https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def extract_article_text_from_html(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    raw_text = unescape(parser.text())
    compact_text = _collapse_whitespace(raw_text)
    lowered = compact_text.lower()
    start = lowered.find("abstract")
    end = lowered.rfind("references")
    if start == -1:
        start = 0
    if end == -1 or end <= start:
        end = len(compact_text)
    return compact_text[start:end].strip()


def _download_text(url: str, timeout: int = 45, max_retries: int = 5) -> str:
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1
        except urllib.error.URLError:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1


def download_pmc_fulltext(
    *,
    papers: list[PaperRecord],
    html_dir: str | Path,
    text_dir: str | Path,
    overwrite: bool,
) -> tuple[list[PaperRecord], dict[str, int]]:
    html_dir = Path(html_dir)
    text_dir = Path(text_dir)
    html_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    updated: list[PaperRecord] = []
    metrics = {
        "total_papers": len(papers),
        "with_pmcid": 0,
        "downloaded": 0,
        "reused_existing": 0,
        "missing_pmcid": 0,
        "failed": 0,
    }

    for paper in papers:
        record = from_dict(PaperRecord, to_dict(paper))
        pmcid = (record.pmcid or "").strip()
        if not pmcid:
            metrics["missing_pmcid"] += 1
            updated.append(record)
            continue

        metrics["with_pmcid"] += 1
        html_path = html_dir / f"{pmcid}.html"
        text_path = text_dir / f"{pmcid}.txt"

        if not overwrite and text_path.exists():
            record.full_text_path = str(text_path.resolve())
            metrics["reused_existing"] += 1
            updated.append(record)
            continue

        try:
            html = _download_text(PMC_ARTICLE_URL.format(pmcid=pmcid))
            ensure_parent(html_path)
            html_path.write_text(html, encoding="utf-8")

            text = extract_article_text_from_html(html)
            if not text:
                raise ValueError(f"Empty article text extracted for {pmcid}")
            ensure_parent(text_path)
            text_path.write_text(text, encoding="utf-8")
            record.full_text_path = str(text_path.resolve())
            metrics["downloaded"] += 1
        except Exception:
            metrics["failed"] += 1
        updated.append(record)

    return updated, metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download PMC full text for harvested papers with PMCID and attach full_text_path.",
    )
    parser.add_argument("--papers", default="artifacts/papers.jsonl")
    parser.add_argument("--output", default="artifacts/papers_with_fulltext.jsonl")
    parser.add_argument("--html-dir", default="artifacts/full_text/html")
    parser.add_argument("--text-dir", default="artifacts/full_text/text")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    papers = [from_dict(PaperRecord, row) for row in read_jsonl(args.papers)]
    updated, metrics = download_pmc_fulltext(
        papers=papers,
        html_dir=args.html_dir,
        text_dir=args.text_dir,
        overwrite=args.overwrite,
    )

    if args.validate_schema:
        schema = load_schema("papers.schema.json")
        for idx, rec in enumerate(updated):
            try:
                validate_record(to_dict(rec), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"papers[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, updated)
    manifest_metrics = dict(metrics)
    manifest_metrics["papers_written"] = count
    outputs = {
        "papers": str(Path(args.output).resolve()),
        "html_dir": str(Path(args.html_dir).resolve()),
        "text_dir": str(Path(args.text_dir).resolve()),
    }
    params = {
        "papers": str(Path(args.papers).resolve()),
        "overwrite": args.overwrite,
    }
    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="download_pmc_fulltext",
        params=params,
        metrics=manifest_metrics,
        outputs=outputs,
        command=" ".join(sys.argv),
    )
    print(
        {
            "output": args.output,
            "metrics": manifest_metrics,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
