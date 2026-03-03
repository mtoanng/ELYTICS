from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SPACES = ("enola", "mycroft", "sherlock", "watson")
SPACE_WATCH_PATHS = (
	"frontend/spaces/{space}/",
	"backend/queries/{space}/",
	"backend/routers/{space}/",
)


@dataclass
class PullRequestInfo:
	pr_id: int
	title: str
	entry_date: str


def _repo_root() -> Path:
	return Path(__file__).resolve().parent.parent


def _normalize(path: str) -> str:
	return path.replace("\\", "/").strip().lstrip("./").lower()


def _changelog_path(area: str, repo_root: Path) -> Path:
	if area == "root":
		return repo_root / "changelog.json"
	return repo_root / "frontend" / "spaces" / area / "changelog.json"


def _default_changelog() -> dict:
	return {"unreleased": [], "releases": {}}


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


def _run_git_changed_files(repo_root: Path) -> list[str]:
	try:
		output = subprocess.check_output(
			["git", "diff", "--name-only", "HEAD~1", "HEAD"],
			cwd=repo_root,
			text=True,
		)
	except Exception:
		return []
	return [line.strip() for line in output.splitlines() if line.strip()]


def _changed_files(repo_root: Path) -> list[str]:
	from_env = os.getenv("CHANGED_FILES", "").strip()
	if from_env:
		candidates = re.split(r"[\n,]", from_env)
		return [item.strip() for item in candidates if item.strip()]
	return _run_git_changed_files(repo_root)


def _extract_pr_from_message(message: str) -> tuple[int | None, str | None]:
	patterns = [
		r"Merged PR\s+(\d+)\s*:\s*(.+)",
		r"Merge pull request\s+#(\d+)\s+from\s+.+\n\n(.+)",
		r"(.+?)\s+\(#(\d+)\)",
	]
	for index, pattern in enumerate(patterns):
		match = re.search(pattern, message, flags=re.IGNORECASE | re.DOTALL)
		if match:
			if index == 2:
				title, pr_id = match.group(1).strip(), match.group(2)
				return int(pr_id), title
			if "Merge pull request" in pattern:
				return int(match.group(1)), match.group(2).strip()
			return int(match.group(1)), match.group(2).strip()
	return None, None


def _pull_request_info() -> PullRequestInfo | None:
	raw_pr = (
		os.getenv("PR_ID")
		or os.getenv("SYSTEM_PULLREQUEST_PULLREQUESTID")
		or ""
	).strip()
	title = (os.getenv("PR_TITLE") or os.getenv("SYSTEM_PULLREQUEST_TITLE") or "").strip()
	entry_date = (os.getenv("PR_DATE") or date.today().isoformat()).strip()

	pr_id: int | None = None
	if raw_pr.isdigit():
		pr_id = int(raw_pr)

	if pr_id is None or not title:
		message = (os.getenv("BUILD_SOURCEVERSIONMESSAGE") or "").strip()
		parsed_pr, parsed_title = _extract_pr_from_message(message)
		pr_id = pr_id or parsed_pr
		title = title or (parsed_title or "")

	if pr_id is None or not title:
		return None

	return PullRequestInfo(pr_id=pr_id, title=title, entry_date=entry_date)


def _determine_areas(changed_files: list[str]) -> set[str]:
	areas: set[str] = set()
	matched_space_paths: set[str] = set()

	for changed in changed_files:
		normalized = _normalize(changed)
		for space in SPACES:
			prefixes = [p.format(space=space) for p in SPACE_WATCH_PATHS]
			if any(normalized.startswith(prefix) for prefix in prefixes):
				areas.add(space)
				matched_space_paths.add(normalized)

	for changed in changed_files:
		normalized = _normalize(changed)
		if normalized in matched_space_paths:
			continue
		if normalized.startswith("frontend/") or normalized.startswith("backend/"):
			areas.add("root")
			break

	return areas


def _has_pr(data: dict, pr_id: int) -> bool:
	unreleased = data.get("unreleased", [])
	if any(item.get("pr") == pr_id for item in unreleased):
		return True
	for entries in data.get("releases", {}).values():
		if any(item.get("pr") == pr_id for item in entries):
			return True
	return False


def main() -> int:
	source_branch = (os.getenv("BUILD_SOURCEBRANCH") or "").strip()
	if source_branch and source_branch != "refs/heads/develop":
		print("Skipping changelog update: branch is not develop.")
		return 0

	repo_root = _repo_root()
	changed_files = _changed_files(repo_root)
	if not changed_files:
		print("No changed files detected; nothing to update.")
		return 0

	pr_info = _pull_request_info()
	if pr_info is None:
		print("PR metadata not found; skipping changelog update.")
		return 0

	target_areas = _determine_areas(changed_files)
	if not target_areas:
		print("No affected areas detected from changed files.")
		return 0

	entry = {"pr": pr_info.pr_id, "title": pr_info.title, "date": pr_info.entry_date}
	updated_paths: list[Path] = []

	for area in sorted(target_areas):
		changelog_file = _changelog_path(area, repo_root)
		changelog_data = _load_changelog(changelog_file)

		if _has_pr(changelog_data, pr_info.pr_id):
			continue

		changelog_data["unreleased"].append(entry)
		_write_changelog(changelog_file, changelog_data)
		updated_paths.append(changelog_file)

	if not updated_paths:
		print("No changelog files required updates.")
		return 0

	print("Updated changelog files:")
	for file_path in updated_paths:
		print(file_path.relative_to(repo_root).as_posix())
	return 0


if __name__ == "__main__":
	raise SystemExit(main())