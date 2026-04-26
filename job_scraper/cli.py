"""Command-line entry point: `python -m job_scraper {init-db|scrape|export|stats}`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import filters, registry
from .db import normalize_db_url
from .pipeline import run
from .storage import Storage

DEFAULT_DB = Path(__file__).resolve().parent.parent / "jobs.db"


def _db_url(args: argparse.Namespace) -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    return normalize_db_url(args.db)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_init_db(args: argparse.Namespace) -> int:
    url = _db_url(args)
    db = Storage(url)
    companies = registry.load_all(args.root)
    n = db.upsert_companies(companies)
    db.close()
    print(f"Initialized {url} with {n} companies.")
    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    companies = registry.load_all(args.root)
    if args.segment:
        wanted = {s.lower() for s in args.segment}
        companies = [c for c in companies if c.segment.lower() in wanted]
    if args.only:
        names = {n.lower() for n in args.only}
        companies = [c for c in companies if c.name.lower() in names]
    if args.limit:
        companies = companies[: args.limit]

    rules = None
    if args.include or args.exclude or args.location:
        rules = filters.FilterRules(
            include=tuple(args.include or ()),
            exclude=tuple(args.exclude or ()),
            locations=tuple(args.location or ()),
        )

    stats = run(
        companies,
        _db_url(args),
        sources=tuple(args.source),
        rules=rules,
        sleep_per_company=args.sleep,
    )
    print(json.dumps(stats.__dict__, indent=2))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with Storage(_db_url(args)) as db:
        print(json.dumps(db.stats(), indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with Storage(_db_url(args)) as db:
        n = db.export_jobs(args.out, only_open=not args.all)
    print(f"Exported {n} jobs -> {args.out}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    from . import resume as resume_mod
    from .matching import match_resume

    text = resume_mod.extract_text(args.resume)
    if not text.strip():
        print("Resume text is empty.", file=sys.stderr)
        return 2
    results = match_resume(text, _db_url(args), top_k=args.top_k, min_score=args.min_score)
    if args.json:
        print(json.dumps([{"score": round(r.score, 4), **r.job} for r in results], indent=2))
    else:
        for r in results:
            j = r.job
            print(f"{r.score:0.3f}  {j['company']:<28}  {j['title'][:60]:<60}  {j['location'][:24]:<24}  {j['url']}")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from alembic import command
    from alembic.config import Config

    cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(cfg_path))
    os.environ.setdefault("DATABASE_URL", _db_url(args))
    if args.action == "upgrade":
        command.upgrade(cfg, args.revision)
        print(f"Upgraded to {args.revision}.")
    elif args.action == "downgrade":
        command.downgrade(cfg, args.revision)
        print(f"Downgraded to {args.revision}.")
    elif args.action == "current":
        command.current(cfg, verbose=True)
    elif args.action == "history":
        command.history(cfg, verbose=True)
    elif args.action == "stamp":
        command.stamp(cfg, args.revision)
        print(f"Stamped {args.revision}.")
    elif args.action == "revision":
        command.revision(cfg, message=args.message, autogenerate=args.autogenerate)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    os.environ.setdefault("DATABASE_URL", _db_url(args))
    uvicorn.run(
        "job_scraper.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="job_scraper")
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="SQLite path or SQLAlchemy URL (env DATABASE_URL overrides)",
    )
    p.add_argument("--root", default=None, help="Folder containing the *_structured.xlsx files")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init-db", help="Create DB and load companies from xlsx files")
    sp.set_defaults(func=cmd_init_db)

    sp = sub.add_parser("scrape", help="Run the scraping pipeline")
    sp.add_argument(
        "--source",
        nargs="+",
        default=["ats", "career"],
        choices=["ats", "career", "playwright", "linkedin"],
    )
    sp.add_argument("--segment", nargs="+", help="Filter by company segment (e.g. Fintech)")
    sp.add_argument("--only", nargs="+", help="Run only the named companies")
    sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--include", nargs="+", help="Keyword(s) to include (any-of, case-insensitive)")
    sp.add_argument("--exclude", nargs="+", help="Keyword(s) to exclude (any-of, case-insensitive)")
    sp.add_argument("--location", nargs="+", help="Substring match against job location")
    sp.add_argument("--sleep", type=float, default=0.4, help="Sleep seconds per company")
    sp.set_defaults(func=cmd_scrape)

    sp = sub.add_parser("stats", help="Show DB stats")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("export", help="Export jobs to .xlsx or .csv")
    sp.add_argument("out")
    sp.add_argument("--all", action="store_true", help="Include closed postings")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("match", help="Score open jobs against a resume (PDF or text)")
    sp.add_argument("resume", help="Path to resume PDF/TXT/MD")
    sp.add_argument("--top-k", type=int, default=25)
    sp.add_argument("--min-score", type=float, default=0.0)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_match)

    sp = sub.add_parser("serve", help="Run the FastAPI dashboard backend")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(func=cmd_serve)

    sp = sub.add_parser("migrate", help="Manage Alembic schema migrations")
    sp.add_argument(
        "action",
        choices=["upgrade", "downgrade", "current", "history", "stamp", "revision"],
    )
    sp.add_argument("revision", nargs="?", default="head", help='Target revision (default "head")')
    sp.add_argument("-m", "--message", default="auto", help="Message for `revision`")
    sp.add_argument("--autogenerate", action="store_true", help="autogenerate diff for `revision`")
    sp.set_defaults(func=cmd_migrate)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
