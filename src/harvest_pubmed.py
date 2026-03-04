from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import PaperRecord, to_dict

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"

DEFAULT_QUERY = (
    "((radiomics[Title/Abstract]) OR (texture analysis[Title/Abstract]) "
    "OR (imaging biomarker[Title/Abstract])) "
    "AND ((computed tomography[Title/Abstract]) OR (CT[Title/Abstract]) "
    "OR (MRI[Title/Abstract]) OR (PET[Title/Abstract]))"
)


def build_query(base_query: str, language: str | None = "english") -> str:
    query = f"({base_query})"
    if language:
        query = f"{query} AND ({language}[Language])"
    return query


def _http_get_json(url: str, params: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(params)
    req_url = f"{url}?{encoded}"
    with urllib.request.urlopen(req_url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get_text(url: str, params: dict[str, Any], timeout: int = 45) -> str:
    encoded = urllib.parse.urlencode(params)
    req_url = f"{url}?{encoded}"
    with urllib.request.urlopen(req_url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def esearch_pubmed(
    *,
    query: str,
    from_year: int,
    to_year: int,
    retmax: int,
    api_key: str | None,
) -> list[str]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax,
        "mindate": f"{from_year}/01/01",
        "maxdate": f"{to_year}/12/31",
        "datetype": "pdat",
    }
    if api_key:
        params["api_key"] = api_key
    payload = _http_get_json(f"{EUTILS_BASE}/esearch.fcgi", params)
    return payload.get("esearchresult", {}).get("idlist", [])


def _first_text(parent: ET.Element, xpath: str) -> str:
    elem = parent.find(xpath)
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _extract_article_year(article: ET.Element) -> int | None:
    for path in (
        "MedlineCitation/Article/ArticleDate/Year",
        "MedlineCitation/Article/Journal/JournalIssue/PubDate/Year",
        "MedlineCitation/DateCompleted/Year",
    ):
        raw = _first_text(article, path)
        if raw.isdigit():
            return int(raw)
    return None


def _extract_abstract(article: ET.Element) -> str:
    parts = []
    for node in article.findall("MedlineCitation/Article/Abstract/AbstractText"):
        txt = "".join(node.itertext()).strip()
        if txt:
            parts.append(txt)
    return " ".join(parts)


def _extract_doi_from_xml(article: ET.Element) -> str | None:
    for node in article.findall("PubmedData/ArticleIdList/ArticleId"):
        if node.attrib.get("IdType") == "doi":
            txt = "".join(node.itertext()).strip()
            return txt or None
    return None


def efetch_pubmed_details(pmids: list[str], api_key: str | None) -> list[dict[str, Any]]:
    if not pmids:
        return []

    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    xml_blob = _http_get_text(f"{EUTILS_BASE}/efetch.fcgi", params)
    root = ET.fromstring(xml_blob)
    articles: list[dict[str, Any]] = []

    for article in root.findall("PubmedArticle"):
        pmid = _first_text(article, "MedlineCitation/PMID")
        if not pmid:
            continue

        parsed = {
            "pmid": pmid,
            "title": _first_text(article, "MedlineCitation/Article/ArticleTitle"),
            "abstract": _extract_abstract(article),
            "journal": _first_text(article, "MedlineCitation/Article/Journal/Title")
            or _first_text(article, "MedlineCitation/Article/Journal/ISOAbbreviation"),
            "year": _extract_article_year(article),
            "language": _first_text(article, "MedlineCitation/Article/Language") or None,
            "doi": _extract_doi_from_xml(article),
        }
        articles.append(parsed)
    return articles


def resolve_pmcid_and_doi(pmids: list[str], timeout: int = 45) -> dict[str, dict[str, str | None]]:
    mapping: dict[str, dict[str, str | None]] = {}
    if not pmids:
        return mapping

    chunk_size = 200
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        params = {"ids": ",".join(chunk), "format": "json"}
        payload = _http_get_json(PMC_IDCONV, params, timeout=timeout)
        for record in payload.get("records", []):
            pmid = record.get("pmid")
            if not pmid:
                continue
            mapping[str(pmid)] = {
                "pmcid": record.get("pmcid"),
                "doi": record.get("doi"),
            }
    return mapping


def collect_papers(
    *,
    query: str,
    from_year: int,
    to_year: int,
    retmax: int,
    api_key: str | None,
) -> list[PaperRecord]:
    retrieval_date = datetime.now(timezone.utc).isoformat()
    pmids = esearch_pubmed(
        query=query,
        from_year=from_year,
        to_year=to_year,
        retmax=retmax,
        api_key=api_key,
    )
    articles = efetch_pubmed_details(pmids, api_key)
    pmc_map = resolve_pmcid_and_doi(pmids)

    results: list[PaperRecord] = []
    for article in articles:
        pmid = article["pmid"]
        mapped = pmc_map.get(pmid, {})
        doi = article.get("doi") or mapped.get("doi")
        rec = PaperRecord(
            pmid=pmid,
            pmcid=mapped.get("pmcid"),
            doi=doi,
            title=article.get("title") or "",
            abstract=article.get("abstract") or "",
            journal=article.get("journal"),
            year=article.get("year"),
            language=article.get("language"),
            query=query,
            retrieval_date=retrieval_date,
            source="pubmed",
        )
        results.append(rec)
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest radiomics-focused papers from PubMed.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="PubMed query body.")
    parser.add_argument("--language", default="english", help="Optional language filter.")
    parser.add_argument("--from-year", type=int, default=2015)
    parser.add_argument("--to-year", type=int, default=datetime.now().year)
    parser.add_argument("--retmax", type=int, default=200)
    parser.add_argument("--output", default="artifacts/papers.jsonl")
    parser.add_argument("--manifest-dir", default="artifacts/manifests")
    parser.add_argument("--ncbi-api-key-env", default="NCBI_API_KEY")
    parser.add_argument("--validate-schema", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = build_query(args.query, args.language)
    api_key = os.getenv(args.ncbi_api_key_env)

    records = collect_papers(
        query=query,
        from_year=args.from_year,
        to_year=args.to_year,
        retmax=args.retmax,
        api_key=api_key,
    )

    if args.validate_schema:
        schema = load_schema("papers.schema.json")
        for idx, rec in enumerate(records):
            try:
                validate_record(to_dict(rec), schema)
            except SchemaValidationError as exc:
                raise SchemaValidationError(f"papers[{idx}] invalid: {exc}") from exc

    count = write_jsonl(args.output, records)

    metrics = {
        "papers_fetched": count,
        "with_abstract": sum(1 for p in records if p.abstract),
        "with_pmcid": sum(1 for p in records if p.pmcid),
        "query": query,
    }
    params = {
        "from_year": args.from_year,
        "to_year": args.to_year,
        "retmax": args.retmax,
        "language": args.language,
        "api_key_used": bool(api_key),
    }
    outputs = {"papers": str(Path(args.output).resolve())}
    write_manifest(
        manifest_dir=args.manifest_dir,
        stage="harvest_pubmed",
        params=params,
        metrics=metrics,
        outputs=outputs,
        command=" ".join(sys.argv),
    )

    print(json.dumps({"output": args.output, "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
