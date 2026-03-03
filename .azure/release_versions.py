from __future__ import annotations

import argparse
import json
from pathlib import Path


SPACES = ("enola", "mycroft", "sherlock", "watson")
RELEASE_TYPES = ("none", "patch", "minor", "major")


def _repo_root() -> Path:
	return Path(__file__).resolve().parent.parent


def _default_changelog() -> dict:
	return {"unreleased": [], "releases": {}}


def _changelog_path(area: str, repo_root: Path) -> Path:
	if area == "root":
		return repo_root / "changelog.json"
	return repo_root / "frontend" / "spaces" / area / "changelog.json"


def _load_changelog(path: Path) -> dict:
	if not path.exists():
		return _default_changelog()
	with path.open("r", encoding="utf-8") as handle:
		data = json.load(handle)
	data.setdefault("unreleased", [])
	data.setdefault("releases", {})
	return data


def _write_changelog(path: Path, data: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as handle:
		json.dump(data, handle, indent=2)
		handle.write("\n")


def _parse_version(version: str) -> tuple[int, int, int]:
	major, minor, patch = version.split(".")
	return int(major), int(minor), int(patch)


def _current_version(releases: dict[str, list[dict]]) -> tuple[int, int, int]:
	if not releases:
		return 0, 0, 0
	versions = [_parse_version(key) for key in releases.keys()]
	return max(versions)


def _format_version(version: tuple[int, int, int]) -> str:
	return f"{version[0]}.{version[1]}.{version[2]}"


def _bump(version: tuple[int, int, int], release_type: str) -> tuple[int, int, int]:
	major, minor, patch = version
	if release_type == "major":
		return major + 1, 0, 0
	if release_type == "minor":
		return major, minor + 1, 0
	if release_type == "patch":
		return major, minor, patch + 1
	return version


def _release_area(area: str, release_type: str, repo_root: Path) -> tuple[bool, str]:
	if release_type == "none":
		return False, f"{area}: skipped (none)."

	changelog_file = _changelog_path(area, repo_root)
	changelog_data = _load_changelog(changelog_file)
	unreleased = changelog_data.get("unreleased", [])

	if not unreleased:
		return False, f"{area}: no unreleased changes, version unchanged."

	releases = changelog_data.get("releases", {})
	current = _current_version(releases)
	next_version = _format_version(_bump(current, release_type))

	if next_version not in releases:
		releases[next_version] = []
	releases[next_version].extend(unreleased)

	changelog_data["unreleased"] = []
	changelog_data["releases"] = releases
	_write_changelog(changelog_file, changelog_data)
	return True, f"{area}: released {len(unreleased)} entries as {next_version}."


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Promote unreleased changelog entries to semantic versions per area."
	)
	parser.add_argument("--root", choices=RELEASE_TYPES, default="none")
	for space in SPACES:
		parser.add_argument(f"--{space}", choices=RELEASE_TYPES, default="none")
	return parser.parse_args()


def main() -> int:
	args = _parse_args()
	repo_root = _repo_root()

	results: list[str] = []
	changed_any = False

	root_changed, root_message = _release_area("root", args.root, repo_root)
	changed_any = changed_any or root_changed
	results.append(root_message)

	for space in SPACES:
		release_type = getattr(args, space)
		changed, message = _release_area(space, release_type, repo_root)
		changed_any = changed_any or changed
		results.append(message)

	for message in results:
		print(message)

	if not changed_any:
		print("No changelog files updated.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())