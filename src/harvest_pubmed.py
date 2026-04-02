from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.artifact_utils import write_jsonl, write_manifest
from src.schema_utils import SchemaValidationError, load_schema, validate_record
from src.types import PaperRecord, to_dict

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
PUBMED_ESEARCH_MAX_IDS = 9998

DEFAULT_QUERY = (
    "((radiomics[Title/Abstract]) OR (texture analysis[Title/Abstract]) "
    "OR (imaging biomarker[Title/Abstract])) "
    "AND ((computed tomography[Title/Abstract]) OR (CT[Title/Abstract]) "
    "OR (MRI[Title/Abstract]) OR (PET[Title/Abstract]))"
)

RADIOMICS_FEATURE_BLOCK_STRICT = (
    "((radiomics[Title/Abstract]) OR (radiomic*[Title/Abstract]) OR "
    "(texture analysis[Title/Abstract]) OR (texture feature*[Title/Abstract]) OR "
    "(glcm[Title/Abstract]) OR (glrlm[Title/Abstract]) OR "
    "(glszm[Title/Abstract]) OR (ngtdm[Title/Abstract]) OR "
    "(gldm[Title/Abstract]) OR "
    "(first-order feature*[Title/Abstract]) OR (shape feature*[Title/Abstract]) OR "
    "(wavelet feature*[Title/Abstract]) OR "
    "(fractal dimension[Title/Abstract]) OR "
    "(laplacian of gaussian[Title/Abstract]) OR (LoG[Title/Abstract]) OR "
    "(quantitative imaging feature*[Title/Abstract]) OR "
    "(radiogenomics[Title/Abstract]) OR (deep radiomics[Title/Abstract]) OR "
    "(run length feature*[Title/Abstract]) OR (histogram feature*[Title/Abstract]) OR "
    "(pyradiomics[Title/Abstract]))"
)

BODYCOMP_FEATURE_BLOCK = (
    "((body composition[Title/Abstract]) OR (body composition analysis[Title/Abstract]) OR "
    "(skeletal muscle index[Title/Abstract]) OR (sarcopenia[Title/Abstract]) OR "
    "(liver surface nodularity[Title/Abstract]) OR (visceral adipose tissue[Title/Abstract]) OR "
    "(visceral adiposity[Title/Abstract]) OR (subcutaneous adipose tissue[Title/Abstract]) OR "
    "(muscle attenuation[Title/Abstract]) OR (muscle mass[Title/Abstract]) OR "
    "(lean mass[Title/Abstract]) OR (fat mass[Title/Abstract]) OR "
    "(psoas area[Title/Abstract]) OR (myosteatosis[Title/Abstract]) OR "
    "(bone mineral density[Title/Abstract]) OR (BMD[Title/Abstract]) OR "
    "(hepatic steatosis[Title/Abstract]) OR (fat fraction[Title/Abstract]) OR "
    "(PDFF[Title/Abstract]) OR (proton density fat fraction[Title/Abstract]) OR "
    "(intramuscular fat[Title/Abstract]) OR (liver fat[Title/Abstract]) OR "
    "(trabecular bone score[Title/Abstract]))"
)

IMAGING_MODALITY_BLOCK_STRICT = (
    "((computed tomography[Title/Abstract]) OR (CT[Title/Abstract]) OR "
    "(magnetic resonance imaging[Title/Abstract]) OR (MRI[Title/Abstract]) OR "
    "(PET[Title/Abstract]) OR (positron emission tomography[Title/Abstract]))"
)

BODYCOMP_MODALITY_BLOCK = (
    "((computed tomography[Title/Abstract]) OR (CT[Title/Abstract]) OR "
    "(magnetic resonance imaging[Title/Abstract]) OR (MRI[Title/Abstract]) OR "
    "(dual-energy x-ray absorptiometry[Title/Abstract]) OR (DXA[Title/Abstract]))"
)

HUMAN_CLINICAL_BLOCK = (
    "((human*[Title/Abstract]) OR (adult*[Title/Abstract]) OR "
    "(patient*[Title/Abstract]) OR (patients[Title/Abstract]) OR "
    "(cohort[Title/Abstract]) OR (clinical[Title/Abstract]) OR "
    "(women[Title/Abstract]) OR (men[Title/Abstract]))"
)

IMAGING_PHENOTYPE_ADJACENT_BLOCK = (
    "((imaging phenotype[Title/Abstract]) OR (imaging phenotypes[Title/Abstract]) OR "
    "(quantitative imaging[Title/Abstract]) OR (quantitative CT[Title/Abstract]) OR "
    "(CT change*[Title/Abstract]) OR (computed tomography change*[Title/Abstract]) OR "
    "(airway lesion*[Title/Abstract]) OR (airway remodeling[Title/Abstract]) OR "
    "(air trapping[Title/Abstract]) OR (emphysema[Title/Abstract]) OR "
    "(radiographic phenotype*[Title/Abstract]) OR (imaging feature*[Title/Abstract]) OR "
    "(3D-CT[Title/Abstract]) OR (3D CT[Title/Abstract]))"
)

MICROBIOME_BLOCK = (
    "((microbiome[Title/Abstract]) OR (microbiota[Title/Abstract]) OR "
    "(gut microbiota[Title/Abstract]) OR (intratumoral microbiome[Title/Abstract]) OR "
    "(intratumoral microbiota[Title/Abstract]) OR (dysbiosis[Title/Abstract]) OR "
    "(alpha diversity[Title/Abstract]) OR (beta diversity[Title/Abstract]) OR "
    "(microbiota composition[Title/Abstract]) OR (microbiome abundance[Title/Abstract]) OR "
    "(microbial signature[Title/Abstract]) OR (microbial signatures[Title/Abstract]) OR "
    "(microbial community[Title/Abstract]) OR "
    "(16S rRNA[Title/Abstract]) OR (metagenomic*[Title/Abstract]) OR "
    "(metagenome[Title/Abstract]) OR (gut flora[Title/Abstract]) OR "
    "(bacteriome[Title/Abstract]) OR (mycobiome[Title/Abstract]) OR "
    "(virome[Title/Abstract]) OR (shotgun metagenomic*[Title/Abstract]) OR "
    "(fecal microbiota transplant*[Title/Abstract]) OR "
    "(microbial diversity[Title/Abstract]))"
)

OUTCOME_SIGNAL_BLOCK = (
    "((predict*[Title/Abstract]) OR (prognosis[Title/Abstract]) OR "
    "(prognostic[Title/Abstract]) OR (diagnosis[Title/Abstract]) OR "
    "(diagnostic[Title/Abstract]) OR (biomarker[Title/Abstract]) OR "
    "(survival[Title/Abstract]) OR (outcome*[Title/Abstract]))"
)

ASSOCIATION_SIGNAL_BLOCK = (
    "((associat*[Title/Abstract]) OR (correlat*[Title/Abstract]))"
)

NON_PRIMARY_ARTICLE_EXCLUSION_BLOCK = (
    "NOT ((review[Publication Type]) OR "
    "(systematic review[Title/Abstract]) OR "
    "(meta-analysis[Title/Abstract]) OR "
    "(protocol[Title/Abstract]) OR "
    "(rationale and design[Title/Abstract]))"
)

MICROBE_RADIOMICS_STRICT_QUERY = (
    f"({RADIOMICS_FEATURE_BLOCK_STRICT} "
    f"AND {IMAGING_MODALITY_BLOCK_STRICT} "
    f"AND {MICROBIOME_BLOCK}) "
    f"{NON_PRIMARY_ARTICLE_EXCLUSION_BLOCK}"
)

MICROBE_BODYCOMP_QUERY = (
    f"({BODYCOMP_FEATURE_BLOCK} "
    f"AND {BODYCOMP_MODALITY_BLOCK} "
    f"AND {MICROBIOME_BLOCK}) "
    f"{NON_PRIMARY_ARTICLE_EXCLUSION_BLOCK}"
)

MICROBE_BODYCOMP_CLINICAL_RECALL_QUERY = (
    f"({BODYCOMP_FEATURE_BLOCK} "
    f"AND {MICROBIOME_BLOCK} "
    f"AND ({ASSOCIATION_SIGNAL_BLOCK} OR {OUTCOME_SIGNAL_BLOCK}) "
    f"AND {HUMAN_CLINICAL_BLOCK}) "
    f"{NON_PRIMARY_ARTICLE_EXCLUSION_BLOCK}"
)

MICROBE_IMAGING_ADJACENT_QUERY = (
    f"({IMAGING_PHENOTYPE_ADJACENT_BLOCK} "
    f"AND {IMAGING_MODALITY_BLOCK_STRICT} "
    f"AND {MICROBIOME_BLOCK}) "
    f"{NON_PRIMARY_ARTICLE_EXCLUSION_BLOCK}"
)

MICROBE_IMAGING_PHENOTYPE_QUERY = (
    f"(({MICROBE_RADIOMICS_STRICT_QUERY}) OR "
    f"({MICROBE_BODYCOMP_QUERY}) OR "
    f"({MICROBE_IMAGING_ADJACENT_QUERY}))"
)

RADIOMICS_DISEASE_STRICT_QUERY = (
    f"{RADIOMICS_FEATURE_BLOCK_STRICT} "
    f"AND {IMAGING_MODALITY_BLOCK_STRICT} "
    f"AND ({OUTCOME_SIGNAL_BLOCK} OR {ASSOCIATION_SIGNAL_BLOCK})"
)

BODYCOMP_DISEASE_QUERY = (
    f"{BODYCOMP_FEATURE_BLOCK} "
    f"AND {BODYCOMP_MODALITY_BLOCK} "
    f"AND {OUTCOME_SIGNAL_BLOCK}"
)

BODYCOMP_DISEASE_ASSOCIATION_QUERY = (
    f"{BODYCOMP_FEATURE_BLOCK} "
    f"AND {BODYCOMP_MODALITY_BLOCK} "
    f"AND ({OUTCOME_SIGNAL_BLOCK} OR {ASSOCIATION_SIGNAL_BLOCK})"
)

QUERY_PROFILES: dict[str, str] = {
    "microbe_radiomics": MICROBE_IMAGING_PHENOTYPE_QUERY,
    "microbe_radiomics_strict": MICROBE_RADIOMICS_STRICT_QUERY,
    "microbe_imaging_adjacent": MICROBE_IMAGING_ADJACENT_QUERY,
    "microbe_imaging_phenotype": MICROBE_IMAGING_PHENOTYPE_QUERY,
    "microbe_bodycomp": MICROBE_BODYCOMP_QUERY,
    "microbe_bodycomp_clinical_recall": MICROBE_BODYCOMP_CLINICAL_RECALL_QUERY,
    "radiomics_disease": RADIOMICS_DISEASE_STRICT_QUERY,
    "radiomics_disease_strict": RADIOMICS_DISEASE_STRICT_QUERY,
    "bodycomp_disease": BODYCOMP_DISEASE_QUERY,
    "bodycomp_disease_association": BODYCOMP_DISEASE_ASSOCIATION_QUERY,
}


def build_query(base_query: str, language: str | None = "english") -> str:
    query = f"({base_query})"
    if language:
        query = f"{query} AND ({language}[Language])"
    return query


def _sleep_for_ncbi(api_key: str | None) -> None:
    # NCBI guidance is stricter without an API key; keep calls polite for large runs.
    time.sleep(0.12 if api_key else 0.34)


def _parse_json_body(body: str) -> dict[str, Any]:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # NCBI occasionally returns control characters inside otherwise valid JSON.
        return json.loads(body, strict=False)


def _date_to_ncbi(value: date) -> str:
    return value.strftime("%Y/%m/%d")


def _midpoint_date(start_date: date, end_date: date) -> date:
    return start_date + timedelta(days=(end_date - start_date).days // 2)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _http_get_json(
    url: str,
    params: dict[str, Any],
    timeout: int = 45,
    max_retries: int = 6,
) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(params)
    req_url = f"{url}?{encoded}"
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req_url, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return _parse_json_body(body)
        except urllib.error.HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= max_retries:
                raise

            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                sleep_s = min(120.0, float(retry_after))
            else:
                sleep_s = min(120.0, float(2**attempt))
            time.sleep(sleep_s)
            attempt += 1
        except urllib.error.URLError:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1
        except json.JSONDecodeError:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1
        except http.client.IncompleteRead:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1


def _esearch_count(
    *,
    query: str,
    start_date: date,
    end_date: date,
    api_key: str | None,
) -> int:
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "mindate": _date_to_ncbi(start_date),
        "maxdate": _date_to_ncbi(end_date),
        "datetype": "pdat",
        "retmax": 0,
        "retstart": 0,
    }
    if api_key:
        params["api_key"] = api_key
    payload = _http_get_json(f"{EUTILS_BASE}/esearch.fcgi", params)
    _sleep_for_ncbi(api_key)
    return int(payload.get("esearchresult", {}).get("count", 0) or 0)


def _esearch_ids_window(
    *,
    query: str,
    start_date: date,
    end_date: date,
    target_total: int,
    api_key: str | None,
) -> list[str]:
    base_params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "mindate": _date_to_ncbi(start_date),
        "maxdate": _date_to_ncbi(end_date),
        "datetype": "pdat",
    }
    if api_key:
        base_params["api_key"] = api_key

    idlist: list[str] = []
    page_size = 5000
    retstart = 0
    while retstart < target_total:
        batch_size = min(page_size, target_total - retstart)
        payload = _http_get_json(
            f"{EUTILS_BASE}/esearch.fcgi",
            {**base_params, "retstart": retstart, "retmax": batch_size},
        )
        _sleep_for_ncbi(api_key)
        batch_ids = payload.get("esearchresult", {}).get("idlist", [])
        if not batch_ids:
            break
        idlist.extend(str(x) for x in batch_ids)
        retstart += len(batch_ids)
    return idlist


def _collect_pmids_for_range(
    *,
    query: str,
    start_date: date,
    end_date: date,
    target_total: int,
    api_key: str | None,
) -> list[str]:
    if target_total <= 0 or start_date > end_date:
        return []

    total_available = _esearch_count(
        query=query,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
    )
    if total_available <= 0:
        return []

    target_total = min(target_total, total_available)
    if total_available <= PUBMED_ESEARCH_MAX_IDS and target_total <= PUBMED_ESEARCH_MAX_IDS:
        return _esearch_ids_window(
            query=query,
            start_date=start_date,
            end_date=end_date,
            target_total=target_total,
            api_key=api_key,
        )

    if start_date >= end_date:
        return _esearch_ids_window(
            query=query,
            start_date=start_date,
            end_date=end_date,
            target_total=min(target_total, PUBMED_ESEARCH_MAX_IDS),
            api_key=api_key,
        )

    mid_date = _midpoint_date(start_date, end_date)
    left_ids = _collect_pmids_for_range(
        query=query,
        start_date=start_date,
        end_date=mid_date,
        target_total=target_total,
        api_key=api_key,
    )
    remaining = target_total - len(left_ids)
    if remaining <= 0:
        return left_ids[:target_total]

    right_start = mid_date + timedelta(days=1)
    right_ids = _collect_pmids_for_range(
        query=query,
        start_date=right_start,
        end_date=end_date,
        target_total=remaining,
        api_key=api_key,
    )
    return _dedupe_preserve_order(left_ids + right_ids)[:target_total]


def _http_get_text(
    url: str,
    params: dict[str, Any],
    timeout: int = 45,
    max_retries: int = 6,
) -> str:
    encoded = urllib.parse.urlencode(params)
    req_url = f"{url}?{encoded}"
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req_url, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            retryable = exc.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= max_retries:
                raise

            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                sleep_s = min(120.0, float(retry_after))
            else:
                sleep_s = min(120.0, float(2**attempt))
            time.sleep(sleep_s)
            attempt += 1
        except urllib.error.URLError:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1
        except http.client.IncompleteRead:
            if attempt >= max_retries:
                raise
            time.sleep(min(60.0, float(2**attempt)))
            attempt += 1


def esearch_pubmed(
    *,
    query: str,
    from_year: int,
    to_year: int,
    retmax: int,
    api_key: str | None,
) -> list[str]:
    start_date = date(from_year, 1, 1)
    end_date = date(to_year, 12, 31)
    total_available = _esearch_count(
        query=query,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
    )
    target_total = total_available if retmax <= 0 else min(retmax, total_available)
    if target_total <= 0:
        return []
    return _collect_pmids_for_range(
        query=query,
        start_date=start_date,
        end_date=end_date,
        target_total=target_total,
        api_key=api_key,
    )


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

    articles: list[dict[str, Any]] = []
    chunk_size = 150
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(chunk),
            "retmode": "xml",
        }
        if api_key:
            params["api_key"] = api_key

        xml_blob = _http_get_text(f"{EUTILS_BASE}/efetch.fcgi", params)
        _sleep_for_ncbi(api_key)
        root = ET.fromstring(xml_blob)

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
                "issn": _first_text(article, "MedlineCitation/Article/Journal/ISSN") or None,
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
        _sleep_for_ncbi(api_key=None)
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
            issn=article.get("issn"),
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
    parser.add_argument(
        "--query-profile",
        choices=["custom", *sorted(QUERY_PROFILES.keys())],
        default="custom",
        help="Preset query profile. Use 'custom' to provide --query explicitly.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="PubMed query body used when --query-profile=custom.",
    )
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
    base_query = QUERY_PROFILES[args.query_profile] if args.query_profile != "custom" else args.query
    query = build_query(base_query, args.language)
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
        "query_profile": args.query_profile,
        "base_query": base_query,
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
