"""`ship` command — the single end-to-end release run.

Orchestrates existing services only (no new framework): bump version → regenerate
project documentation (CHANGELOG / RELEASE_NOTES / PROJECT_STATUS) → group, commit
and push working-tree changes (optional tag) → verify and display version, commit
hash and repository URL.
"""

from __future__ import annotations

import argparse

from ..core.result import CommandResult
from .base import add_common_arguments, build_container, run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="automation.ship",
        description="Update version + docs, then commit and push in one command.",
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch", "build"],
        default="build",
        help="Version level to increment (default: build).",
    )
    parser.add_argument("--no-bump", action="store_true", help="Do not change the version.")
    parser.add_argument("--tag", action="store_true", help="Create and push a version tag.")
    parser.add_argument("--no-push", action="store_true", help="Commit only; do not push.")
    return parser


def _handle(args: argparse.Namespace) -> CommandResult:
    container = build_container(args)
    git = container.git

    if not git.is_repository():
        return CommandResult.failure(
            "Not inside a git repository. Run 'git init' and add the 'origin' remote first."
        )

    changed: list[str] = []

    # 1. Version
    if not args.no_bump:
        changed += container.version_service.bump(args.bump).changed_paths

    # 2. Project documentation (framework-generated artifacts)
    changed += container.release_service.build(create_tag=False).changed_paths
    changed += container.dashboard_service.build().changed_paths

    # 3. Add → commit → push (+ optional tag)
    sync = container.github_sync_service.sync(create_tag=args.tag, push=not args.no_push)
    if not sync.ok:
        return sync

    # 4. Verify + display
    version = container.version_service.current()
    commit = git.short_commit() or "n/a"
    branch = git.current_branch()
    repo_url = container.config.project.get("repository", "n/a")
    pushed = bool(sync.data.get("pushed", False))

    summary = "\n".join(
        [
            "Release automation complete.",
            f"   Version    : {version.semver} (build {version.build_number}) — {version.release_name}",
            f"   Commit     : {commit} on {branch}",
            f"   Push       : {'verified' if pushed else 'skipped (--no-push)'}",
            f"   Repository : {repo_url}",
        ]
    )
    return CommandResult.success(
        summary,
        changed_paths=changed,
        data={"version": version.full, "commit": commit, "branch": branch,
              "repository": repo_url, "pushed": pushed},
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return run(_handle, args)
