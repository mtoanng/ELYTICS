from __future__ import annotations

from typing import Any
import json
from pathlib import Path

import dash_mantine_components as dmc


def _format_item(item: Any) -> dict[str, Any] | None:
	if isinstance(item, str):
		return {"text": item, "date": None}
	if isinstance(item, dict):
		title = item.get("title") or item.get("text") or item.get("summary") or ""
		pr = item.get("pr")
		date = item.get("date")
		if title and pr:
			return {"text": f"{title} (#{pr})", "date": date}
		if title:
			return {"text": title, "date": date}
		if pr:
			return {"text": f"PR #{pr}", "date": date}
	return None


def load_changelog_json(changelog_path: Path) -> dict[str, Any]:
	if not changelog_path.exists():
		return {}
	with changelog_path.open(encoding="utf-8") as handle:
		return json.load(handle)


def _normalize_changelog(changelog: dict[str, Any] | None) -> list[dict[str, Any]]:
	if not isinstance(changelog, dict):
		return []

	updates: list[dict[str, Any]] = []

	unreleased = changelog.get("unreleased") or []
	if isinstance(unreleased, list) and unreleased:
		changes = [
			formatted
			for item in unreleased
			if (formatted := _format_item(item))
		]
		updates.append(
			{
				"version": "Unreleased",
				"status": "Work in progress",
				"date": None,
				"changes": changes,
			}
		)

	releases = changelog.get("releases") or {}
	if isinstance(releases, dict):
		for version, payload in releases.items():
			date = None
			raw_changes: list[Any] = []
			if isinstance(payload, dict):
				date = (
					payload.get("date")
					or payload.get("released")
					or payload.get("released_at")
				)
				raw_changes = (
					payload.get("changes")
					or payload.get("items")
					or payload.get("entries")
					or []
				)
			elif isinstance(payload, list):
				raw_changes = payload

			changes = [
				formatted
				for item in raw_changes
				if (formatted := _format_item(item))
			]
			updates.append(
				{
					"version": version,
					"status": "Released",
					"date": date,
					"changes": changes,
				}
			)
	elif isinstance(releases, list):
		for payload in releases:
			if not isinstance(payload, dict):
				continue
			version = payload.get("version") or payload.get("tag") or "Release"
			date = payload.get("date") or payload.get("released")
			raw_changes = (
				payload.get("changes")
				or payload.get("items")
				or payload.get("entries")
				or []
			)
			changes = [
				formatted
				for item in raw_changes
				if (formatted := _format_item(item))
			]
			updates.append(
				{
					"version": version,
					"status": "Released",
					"date": date,
					"changes": changes,
				}
			)

	return updates


def _create_update_log_item(update: dict[str, Any], source_label: str, source_color: str):
	status_lower = update.get("status", "").lower()
	is_wip = "work in progress" in status_lower or "wip" in status_lower
	changes = update.get("changes") or []
	change_dates = [change.get("date") for change in changes if change.get("date")]
	latest_date = max(change_dates, default=update.get("date"))
	date_text = latest_date or "N/A"

	feature_changes: list[dict[str, Any]] = []
	fix_changes: list[dict[str, Any]] = []
	other_changes: list[dict[str, Any]] = []
	for change in changes:
		text = (change.get("text") or "").strip()
		text_lower = text.lower()
		if text_lower.startswith("feat"):
			feature_changes.append(change)
		elif text_lower.startswith("fix"):
			fix_changes.append(change)
		else:
			other_changes.append(change)

	def _render_change_list(title: str, items: list[dict[str, Any]]) -> list[dmc.Component]:
		if not items:
			return []
		return [
			dmc.Text(title, fw=600, size="sm", mt="sm"),
			dmc.List(
				[
					dmc.ListItem(item['text'])
					for item in items
				],
				spacing="xs",
				size="sm",
				mt="xs",
			),
		]

	status_label = "Work in progress" if is_wip else "Released"
	status_color = "yellow" if is_wip else "green"
	return dmc.Paper(
		[
			dmc.Group(
				[
					dmc.Group(
						[
							dmc.Badge(
								source_label,
								color=source_color,
								variant="light",
							),
							dmc.Badge(
								status_label,
								color=status_color,
								variant="light",
							),
							dmc.Badge(
								update.get("version", ""),
								color="green",
								variant="dot",
							),
						],
						gap="xs",
					),
					dmc.Text(
						date_text,
						size="sm",
						c="dimmed",
					),
				],
				justify="space-between",
			),
			*(_render_change_list("New Features", feature_changes)),
			*(_render_change_list("Bug Fixes", fix_changes)),
			*(_render_change_list("Other Changes", other_changes)),
			*([
				dmc.List(
					[dmc.ListItem("No updates yet")],
					spacing="xs",
					size="sm",
					mt="sm",
				)
			] if not changes else []),
		],
		p="md",
		radius="md",
		withBorder=True,
		maw=760,
	)


def build_update_cards(
	changelog: dict[str, Any] | None,
	source_label: str,
	source_color: str,
) -> list[dmc.Component]:
	updates = _normalize_changelog(changelog)
	return [
		_create_update_log_item(update, source_label, source_color)
		for update in updates
	]
