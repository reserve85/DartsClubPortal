"""Version and build information (same pattern as EloRankingSystem).

Values are injected during the Docker build via ARG/ENV and fall back to
sensible defaults for local development.
"""

import os
from datetime import datetime

GITHUB_REPO_URL = "https://github.com/reserve85/DartsClubPortal"


def get_version_info(timezone: str = "UTC") -> dict:
    """Get version, git commit, and build date info.

    Args:
        timezone: IANA timezone name for build date formatting.

    Returns:
        Dict with version, git_commit, build_date, github_url, release_url.
    """
    raw_version = os.getenv("APP_VERSION", "0.1.0")
    # Strip a leading build-tag "v" ("v1.2.3") — but only when the remainder
    # actually looks like a version (starts with a digit), so arbitrary strings
    # are never corrupted.
    version = raw_version
    candidate = version.lstrip("v")
    if candidate[:1].isdigit():
        version = candidate

    full_commit = os.getenv("GIT_COMMIT", "dev")
    git_commit = full_commit[:7]

    raw_build_date = os.getenv("BUILD_DATE", "development")
    build_date = _format_build_date(raw_build_date, timezone)
    build_day = _build_day(raw_build_date, timezone)

    # Link to the exact release tag for version builds; non-version builds
    # (e.g. "main"/"dev" images) fall back to the releases overview so the
    # footer link never points to a non-existent tag.
    release_url = (
        f"{GITHUB_REPO_URL}/releases/tag/v{version}"
        if version[:1].isdigit()
        else f"{GITHUB_REPO_URL}/releases"
    )

    return {
        "version": version,
        "git_commit": git_commit,
        "build_date": build_date,
        "build_day": build_day,
        "github_url": GITHUB_REPO_URL,
        "release_url": release_url,
        # Link of the build commit; only for a real commit hash.
        "commit_url": (
            f"{GITHUB_REPO_URL}/commit/{full_commit}"
            if len(full_commit) >= 7 and all(c in "0123456789abcdef" for c in full_commit)
            else ""
        ),
    }


def _build_day(raw: str, timezone: str) -> str:
    """Local build date as ISO "YYYY-MM-DD" ("" for development builds)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.fromisoformat(raw).astimezone(ZoneInfo(timezone)).date().isoformat()
    except (ValueError, KeyError, OSError):
        return ""


def _format_build_date(raw: str, timezone: str) -> str:
    """Format build date string using the configured timezone.

    Args:
        raw: Build date string (ISO 8601 or 'development').
        timezone: IANA timezone name.

    Returns:
        Formatted date string in the given timezone.
    """
    if raw == "development":
        return "development"

    try:
        from zoneinfo import ZoneInfo

        dt = datetime.fromisoformat(raw)
        tz = ZoneInfo(timezone)
        dt_local = dt.astimezone(tz)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    except (ValueError, ImportError, KeyError, OSError):
        return raw
