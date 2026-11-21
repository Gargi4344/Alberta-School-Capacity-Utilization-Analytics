"""Download the public source files into data/raw/.

CKAN datasets are resolved through the open.alberta.ca API, so every school-year
file the ministry publishes is fetched. ArcGIS layers are queried as GeoJSON in
WGS 84 (EPSG:4326), paging through results when a layer exceeds the server limit.

Every download is recorded in data/raw/manifest.json (URL, size, SHA-256), so a
run can be reproduced and checked later.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlparse

import httpx
import yaml

log = logging.getLogger("pipeline.download")

SOURCES_FILE = Path(__file__).with_name("sources.yaml")
_YEAR_RE = re.compile(r"(20\d{2})\s*[/-]\s*(20\d{2}|\d{2})")


@dataclass(frozen=True)
class CkanResource:
    key: str
    name: str
    url: str
    format: str
    filename: str
    school_year: str | None
    last_modified: str | None


@dataclass
class ManifestEntry:
    key: str
    path: str
    url: str
    bytes: int
    sha256: str
    downloaded_at: str
    school_year: str | None = None
    source_modified: str | None = None
    features: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def parse_school_year(text: str) -> str | None:
    """Return a school year as 'YYYY-YY' from text like '2025/2026' or '2016-17'."""
    match = _YEAR_RE.search(text)
    if not match:
        return None
    start, end = int(match.group(1)), match.group(2)
    end_two = int(end[-2:])
    if end_two != (start + 1) % 100:
        return None
    return f"{start}-{end_two:02d}"


def select_resources(package: dict[str, Any], key: str, formats: list[str]) -> list[CkanResource]:
    """Pick the downloadable resources of a CKAN package that match the wanted formats."""
    wanted = {f.upper() for f in formats}
    out: list[CkanResource] = []
    for res in package.get("resources", []):
        fmt = (res.get("format") or "").upper()
        url = res.get("url") or ""
        if fmt not in wanted or not url:
            continue
        filename = unquote(Path(urlparse(url).path).name)
        name = res.get("name") or filename
        out.append(
            CkanResource(
                key=key,
                name=name,
                url=url,
                format=fmt,
                filename=filename,
                school_year=parse_school_year(name) or parse_school_year(filename),
                last_modified=res.get("last_modified") or res.get("metadata_modified"),
            )
        )
    return sorted(out, key=lambda r: (r.school_year or "", r.filename))


def arcgis_query_url(layer_url: str, offset: int = 0, page_size: int = 1000) -> str:
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
    }
    return f"{layer_url.rstrip('/')}/query?{urlencode(params)}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


def _get(client: httpx.Client, url: str, attempts: int = 3) -> httpx.Response:
    for attempt in range(1, attempts + 1):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == attempts:
                raise
            wait = 2**attempt
            log.warning("retrying", extra={"url": url, "attempt": attempt, "error": str(exc)})
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _stream_to(client: httpx.Client, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(1 << 16):
                fh.write(chunk)
    tmp.replace(dest)


def fetch_ckan_package(client: httpx.Client, base_url: str, package: str) -> dict[str, Any]:
    resp = _get(client, f"{base_url.rstrip('/')}/package_show?id={package}")
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"CKAN package_show failed for {package}: {body.get('error')}")
    return body["result"]


def fetch_arcgis_geojson(client: httpx.Client, layer_url: str) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _get(client, arcgis_query_url(layer_url, offset)).json()
        if "error" in page:
            raise RuntimeError(f"ArcGIS error for {layer_url}: {page['error']}")
        batch = page.get("features", [])
        features.extend(batch)
        exceeded = page.get("exceededTransferLimit") or page.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if not batch or not exceeded:
            break
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def load_sources(path: Path = SOURCES_FILE) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> dict[str, ManifestEntry]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {e["path"]: ManifestEntry(**e) for e in data.get("files", [])}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def download_all(
    raw_dir: Path,
    ckan_base_url: str,
    run_id: str,
    *,
    force: bool = False,
    include_optional: bool = True,
    timeout: float = 120.0,
) -> list[ManifestEntry]:
    sources = load_sources()
    manifest_path = raw_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    raw_dir.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "ab-capacity-pipeline/0.1 (open-data research)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for ds in sources.get("ckan_datasets", []):
            package = fetch_ckan_package(client, ckan_base_url, ds["package"])
            resources = select_resources(package, ds["key"], ds.get("formats", ["XLSX"]))
            log.info(
                "ckan package resolved",
                extra={"run_id": run_id, "package": ds["package"], "resources": len(resources)},
            )
            for res in resources:
                rel = f"{ds['dest']}/{res.filename}"
                dest = raw_dir / rel
                prev = manifest.get(rel)
                if (
                    not force
                    and dest.exists()
                    and prev
                    and prev.url == res.url
                    and prev.source_modified == res.last_modified
                ):
                    log.info("skip (unchanged)", extra={"run_id": run_id, "path": rel})
                    continue
                _stream_to(client, res.url, dest)
                manifest[rel] = ManifestEntry(
                    key=res.key,
                    path=rel,
                    url=res.url,
                    bytes=dest.stat().st_size,
                    sha256=sha256_of(dest),
                    downloaded_at=_now(),
                    school_year=res.school_year,
                    source_modified=res.last_modified,
                    extra={"resource_name": res.name, "licence": package.get("license_title")},
                )
                log.info(
                    "downloaded",
                    extra={"run_id": run_id, "path": rel, "bytes": manifest[rel].bytes},
                )

        for layer in sources.get("arcgis_layers", []):
            if layer.get("optional") and not include_optional:
                continue
            rel = layer["dest"]
            dest = raw_dir / rel
            if dest.exists() and rel in manifest and not force:
                log.info("skip (exists)", extra={"run_id": run_id, "path": rel})
                continue
            try:
                fc = fetch_arcgis_geojson(client, layer["url"])
            except (httpx.HTTPError, RuntimeError) as exc:
                if layer.get("optional"):
                    log.warning("optional layer failed", extra={"path": rel, "error": str(exc)})
                    continue
                raise
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(fc), encoding="utf-8")
            manifest[rel] = ManifestEntry(
                key=layer["key"],
                path=rel,
                url=layer["url"],
                bytes=dest.stat().st_size,
                sha256=sha256_of(dest),
                downloaded_at=_now(),
                features=len(fc["features"]),
                extra={"licence": layer.get("licence", "Open Government Licence - Alberta")},
            )
            log.info(
                "downloaded layer",
                extra={"run_id": run_id, "path": rel, "features": len(fc["features"])},
            )

    entries = sorted(manifest.values(), key=lambda e: e.path)
    manifest_path.write_text(
        json.dumps(
            {"run_id": run_id, "generated_at": _now(), "files": [asdict(e) for e in entries]},
            indent=2,
        ),
        encoding="utf-8",
    )
    return entries
