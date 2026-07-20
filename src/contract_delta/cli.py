"""Command-line entrypoint for live updates and deterministic fixture builds."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from contract_delta.backfill import BackfillError, run_backfill
from contract_delta.client import AusTenderClient
from contract_delta.models import CollectionCoverage
from contract_delta.pipeline import process_releases, rebuild_site, write_public_status
from contract_delta.source_links import SourceLinkError, check_dashboard_source_links


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _bounded_integer(value: str, *, name: str, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
    if not 1 <= parsed <= maximum:
        raise argparse.ArgumentTypeError(f"{name} must be between 1 and {maximum}")
    return parsed


def _lookback_days(value: str) -> int:
    return _bounded_integer(value, name="lookback days", maximum=31)


def _max_pages(value: str) -> int:
    return _bounded_integer(value, name="max pages", maximum=250)


def _max_amended_contracts(value: str) -> int:
    return _bounded_integer(value, name="maximum amended contracts", maximum=500)


def _window_days(value: str) -> int:
    return _bounded_integer(value, name="window days", maximum=31)


def _max_windows(value: str) -> int:
    return _bounded_integer(value, name="maximum windows", maximum=53)


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
    parser.add_argument(
        "--data-root",
        type=_root,
        help="private durable-data checkout; defaults to the repository root",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    live = subparsers.add_parser("update", help="fetch a live latest-modified date range")
    live.add_argument("--from", dest="start", type=_date)
    live.add_argument("--to", dest="end", type=_date)
    live.add_argument("--lookback-days", type=_lookback_days, default=8)
    live.add_argument("--max-pages", type=_max_pages, default=250)
    live.add_argument("--no-hydrate", action="store_true")
    live.add_argument(
        "--amendments-only",
        action="store_true",
        help="process only an explicitly bounded set of amendment contracts",
    )
    live.add_argument(
        "--max-amended-contracts",
        type=_max_amended_contracts,
        default=20,
    )

    backfill = subparsers.add_parser(
        "backfill",
        help="resume a bounded historical amendment collection",
    )
    backfill.add_argument("--from", dest="start", type=_date, required=True)
    backfill.add_argument("--to", dest="end", type=_date, required=True)
    backfill.add_argument("--window-days", type=_window_days, default=7)
    backfill.add_argument("--max-windows", type=_max_windows, default=1)
    backfill.add_argument("--max-pages", type=_max_pages, default=250)
    backfill.add_argument(
        "--max-amended-contracts",
        type=_max_amended_contracts,
        default=20,
    )

    fixture = subparsers.add_parser("ingest-fixture", help="process saved OCDS packages")
    fixture.add_argument("path", type=Path)

    subparsers.add_parser("rebuild-site", help="rebuild site assets from local state")
    status = subparsers.add_parser(
        "publish-status",
        help="write non-identifying public update metadata from private state",
    )
    status.add_argument("--data-revision")
    subparsers.add_parser(
        "check-source-links",
        help="check generated official-record and OCDS JSON destinations",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    data_root: Path = args.data_root or root
    if args.command == "rebuild-site":
        dashboard = rebuild_site(root, data_root=data_root)
        print(json.dumps(dashboard["stats"], default=str, sort_keys=True))
        return 0
    if args.command == "publish-status":
        status = write_public_status(
            root,
            data_root=data_root,
            data_revision=args.data_revision,
        )
        print(json.dumps(status, default=str, sort_keys=True))
        return 0
    if args.command == "check-source-links":
        try:
            report = check_dashboard_source_links(root / "site/src/data/dashboard.json")
        except SourceLinkError as exc:
            print(f"source link check failed: {exc}")
            return 1
        for result in report.results:
            status = str(result.status_code) if result.status_code is not None else result.detail
            print(f"{result.outcome.upper():13} {status or '-':18} {result.url}")
        print(
            "source link check: "
            f"{report.reachable} reachable, {report.broken} broken, "
            f"{report.indeterminate} indeterminate; "
            f"{report.checked} checked of {report.discovered} discovered"
        )
        return 1 if report.broken else 0

    if args.command == "backfill":
        try:
            with AusTenderClient(max_pages=args.max_pages) as client:
                checkpoint, path = run_backfill(
                    client,
                    root=root,
                    data_root=data_root,
                    start_date=args.start,
                    end_date=args.end,
                    window_days=args.window_days,
                    max_windows=args.max_windows,
                    max_amended_contracts=args.max_amended_contracts,
                )
        except BackfillError as exc:
            print(f"backfill failed: {exc}")
            return 1
        payload = checkpoint.model_dump(mode="json")
        payload["checkpoint_path"] = str(path)
        print(json.dumps(payload, indent=2, default=str, sort_keys=True))
        return 0

    if args.command == "ingest-fixture":
        releases, urls, license_url, publisher = _read_fixture(args.path)
        result = process_releases(
            releases,
            root=root,
            data_root=data_root,
            source_urls=urls,
            source_license=license_url,
            source_publisher=publisher,
            pages_fetched=len(urls),
            coverage=CollectionCoverage(
                mode="fixture",
                selection_method="All releases in the saved fixture were processed.",
            ),
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
                amendments_only=args.amendments_only,
                max_amended_contracts=(
                    args.max_amended_contracts if args.amendments_only else None
                ),
            )
        result = process_releases(
            fetched.releases,
            root=root,
            data_root=data_root,
            source_urls=fetched.source_urls,
            source_license=fetched.license_url,
            source_publisher=fetched.publisher,
            pages_fetched=fetched.pages_fetched,
            coverage=fetched.coverage(),
        )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
