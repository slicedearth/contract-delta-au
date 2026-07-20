"""Command-line entrypoint for live updates and deterministic fixture builds."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from contract_delta.client import AusTenderClient
from contract_delta.pipeline import process_releases, rebuild_site


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _read_fixture(path: Path) -> tuple[list[dict[str, Any]], list[str], str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    packages = payload if isinstance(payload, list) else [payload]
    releases: list[dict[str, Any]] = []
    source_urls: list[str] = []
    license_url = "https://creativecommons.org/licenses/by/3.0/au/"
    publisher = "Australian Government Department of Finance"
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError("fixture packages must be JSON objects")
        releases.extend(package.get("releases") or [])
        if package.get("uri"):
            source_urls.append(str(package["uri"]))
        license_url = str(package.get("license") or license_url)
        publisher = str((package.get("publisher") or {}).get("name") or publisher)
    return releases, source_urls, license_url, publisher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract-delta",
        description="Detect evidence-linked changes in AusTender Contract Notices.",
    )
    parser.add_argument("--root", type=_root, default=Path.cwd(), help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    live = subparsers.add_parser("update", help="fetch a live latest-modified date range")
    live.add_argument("--from", dest="start", type=_date)
    live.add_argument("--to", dest="end", type=_date)
    live.add_argument("--lookback-days", type=int, default=8)
    live.add_argument("--max-pages", type=int, default=250)
    live.add_argument("--no-hydrate", action="store_true")

    fixture = subparsers.add_parser("ingest-fixture", help="process saved OCDS packages")
    fixture.add_argument("path", type=Path)

    subparsers.add_parser("rebuild-site", help="rebuild site assets from local state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    if args.command == "rebuild-site":
        dashboard = rebuild_site(root)
        print(json.dumps(dashboard["stats"], default=str, sort_keys=True))
        return 0

    if args.command == "ingest-fixture":
        releases, urls, license_url, publisher = _read_fixture(args.path)
        result = process_releases(
            releases,
            root=root,
            source_urls=urls,
            source_license=license_url,
            source_publisher=publisher,
            pages_fetched=len(urls),
        )
    else:
        today = datetime.now(UTC).date()
        start_date = args.start or (today - timedelta(days=args.lookback_days))
        end_date = args.end or today
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date, time.max, tzinfo=UTC)
        with AusTenderClient(max_pages=args.max_pages) as client:
            fetched = client.fetch_modified(
                start,
                end,
                hydrate_amendments=not args.no_hydrate,
            )
        result = process_releases(
            fetched.releases,
            root=root,
            source_urls=fetched.source_urls,
            source_license=fetched.license_url,
            source_publisher=fetched.publisher,
            pages_fetched=fetched.pages_fetched,
        )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
