def get_latest_released_version():
    """
    Returns the version string of the latest entry with status 'Released' in CHANGELOG.md.
    """
    versions = parse_changelog()
    for v in versions:
        if v.get("status", "").lower() == "released":
            return v["version"]
    return None
import os
import re

CHANGELOG_PATH = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")

def get_latest_changelog_version():
    """
    Returns the first version string found in a '##' header in CHANGELOG.md.
    """
    if not os.path.exists(CHANGELOG_PATH):
        return None
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        for line in f:
            match = re.match(r"^##\s*([^\n]+)", line)
            if match:
                version_line = match.group(1).strip()
                version_match = re.match(r"([^\(]+)", version_line)
                if version_match:
                    return version_match.group(1).strip()
                return version_line
    return None

def parse_changelog():
    """
    Parses CHANGELOG.md and returns a list of dicts:
    [
        {
            "version": "1.1.0",
            "status": "Planned",
            "items": ["feature a", "feature b"]
        },
        ...
    ]
    """
    if not os.path.exists(CHANGELOG_PATH):
        return []
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    versions = []
    current = None
    bullet_re = re.compile(r'^(\s*)- (.*)')
    for line in lines:
        header = re.match(r"^##\s*(.+)", line)
        if header:
            if current:
                versions.append(current)
            title = header.group(1).strip()
            m = re.match(r"(.+?)\s*\((.+)\)", title)
            if m:
                version, status = m.group(1).strip(), m.group(2).strip()
            else:
                version, status = title, ""
            current = {"version": version, "status": status, "items": []}
            stack = [(0, current["items"])]  # (indent, list)
        else:
            m = bullet_re.match(line)
            if m and current:
                indent = len(m.group(1).replace('\t', '    '))
                text = m.group(2).strip()
                # Find where to insert based on indent
                while stack and indent < stack[-1][0]:
                    stack.pop()
                if indent > stack[-1][0]:
                    # New sublist
                    new_list = []
                    # Attach to last item of previous list
                    if stack[-1][1]:
                        if isinstance(stack[-1][1][-1], str):
                            stack[-1][1][-1] = [stack[-1][1][-1]]
                        if isinstance(stack[-1][1][-1], list):
                            stack[-1][1][-1].append(new_list)
                    stack.append((indent, new_list))
                    new_list.append(text)
                else:
                    stack[-1][1].append(text)
    if current:
        versions.append(current)
    # Post-process: flatten single-item lists
    def flatten(items):
        out = []
        for item in items:
            if isinstance(item, list) and len(item) == 1:
                out.append(item[0])
            else:
                out.append(item)
        return out
    for v in versions:
        v["items"] = flatten(v["items"])
    return versions
