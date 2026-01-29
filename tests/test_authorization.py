import ast
import os
import pytest

# Map directory to required group
ACCESS_POLICY = {
    "watson": "IdM2BCD_holmes_pemely_user",
    "sherlock": "IdM2BCD_holmes_pemely_user",
    "mycroft": "IdM2BCD_holmes_pemely_user",
    "enola": "IdM2BCD_holmes_pemely_management",
}

SPACES_DIR = os.path.join(os.path.dirname(__file__), "..", "spaces")

def get_protected_groups_from_file(filepath):
    """Parse a Python file and return a list of groups used in @protected decorators."""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)
    groups = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and getattr(decorator.func, 'id', None) == "protected":
                    for kw in decorator.keywords:
                        if kw.arg == "groups":
                            # For Python 3.8+, ast.Constant is used for strings
                            if isinstance(kw.value, ast.List):
                                group_values = [
                                    elt.value for elt in kw.value.elts
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                                ]
                                groups.extend(group_values)
    return groups

@pytest.mark.parametrize("section,required_group", ACCESS_POLICY.items())
def test_section_group_protection(section, required_group):
    section_dir = os.path.join(SPACES_DIR, section)
    assert os.path.isdir(section_dir), f"Section directory missing: {section_dir}"
    for root, _, files in os.walk(section_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                groups = get_protected_groups_from_file(filepath)
                assert required_group in groups, (
                    f"{filepath} is missing required group '{required_group}' in @protected decorator"
                )