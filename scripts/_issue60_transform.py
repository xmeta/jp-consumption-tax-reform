#!/usr/bin/env python3
"""One-shot Issue #60 migration; removed before the final branch commit."""
from pathlib import Path
import ast
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GUARD_MESSAGE = "optimized Python is not supported for executable tests; assertions must remain active"


def tracked_python_files():
    return subprocess.check_output(
        ["git", "ls-files", "*.py"], cwd=ROOT, text=True
    ).splitlines()


def offsets_for(source_bytes):
    starts = [0]
    for line in source_bytes.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


def transform_production(rel):
    path = ROOT / rel
    source_bytes = path.read_bytes()
    source = source_bytes.decode("utf-8")
    tree = ast.parse(source, filename=rel)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    if not nodes:
        return 0
    starts = offsets_for(source_bytes)
    replacements = []
    for node in nodes:
        start = starts[node.lineno - 1] + node.col_offset
        end = starts[node.end_lineno - 1] + node.end_col_offset
        prefix = source_bytes[starts[node.lineno - 1]:start]
        if prefix.strip():
            raise RuntimeError(f"unsafe non-leading production assert: {rel}:{node.lineno}")
        indent = prefix.decode("utf-8")
        expression = ast.unparse(node.test)
        if node.msg is None:
            message = repr(f"scientific runtime invariant failed: {rel}:{node.lineno}")
        else:
            message = ast.unparse(node.msg)
        replacement = (
            f"if not ({expression}):\n"
            f"{indent}    raise RuntimeError({message})"
        ).encode("utf-8")
        replacements.append((start, end, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        source_bytes = source_bytes[:start] + replacement + source_bytes[end:]
    transformed = source_bytes.decode("utf-8")
    check = ast.parse(transformed, filename=rel)
    if any(isinstance(n, ast.Assert) for n in ast.walk(check)):
        raise RuntimeError(f"production assert remained after transform: {rel}")
    path.write_text(transformed, encoding="utf-8")
    return len(nodes)


def guard_insertion_line(source, tree):
    lines = source.splitlines(keepends=True)
    header_end = 0
    if lines and lines[0].startswith("#!"):
        header_end = 1
    if header_end < len(lines) and header_end < 2 and re.search(r"coding[:=]", lines[header_end]):
        header_end += 1
    insert_after = header_end
    body = list(tree.body)
    index = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        insert_after = max(insert_after, body[0].end_lineno)
        index = 1
    while index < len(body) and isinstance(body[index], ast.ImportFrom) and body[index].module == "__future__":
        insert_after = max(insert_after, body[index].end_lineno)
        index += 1
    return insert_after


def guard_test(rel):
    path = ROOT / rel
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    if not nodes:
        return 0
    if GUARD_MESSAGE in source:
        return len(nodes)
    lines = source.splitlines(keepends=True)
    insert_at = guard_insertion_line(source, tree)
    guard = (
        "\nif not __debug__:\n"
        f"    raise RuntimeError({GUARD_MESSAGE!r})\n"
    )
    lines[insert_at:insert_at] = [guard]
    transformed = "".join(lines)
    ast.parse(transformed, filename=rel)
    path.write_text(transformed, encoding="utf-8")
    return len(nodes)


def write_regression_test():
    path = ROOT / "scripts/test_python_optimized_runtime_guards.py"
    path.write_text('''#!/usr/bin/env python3\nfrom pathlib import Path\nimport ast\nimport csv\nimport io\nimport subprocess\nimport sys\n\nROOT = Path(__file__).resolve().parents[1]\nGUARD_MESSAGE = "optimized Python is not supported for executable tests; assertions must remain active"\nTARGET_SOURCE = "ESRI-SNA-2024-NOMINAL-GDP-FISCAL-YEAR"\nBUILDER = ROOT / "research/vat_policy_integration/build_jgb_debt_gdp_reference.py"\nCATALOG = ROOT / "data/source_catalog.csv"\n\ndef require(condition, message):\n    if not condition:\n        raise RuntimeError(message)\n\ndef tracked_python_files():\n    return subprocess.check_output(["git", "ls-files", "*.py"], cwd=ROOT, text=True).splitlines()\n\ndef is_optimized_guard(node):\n    return (\n        isinstance(node, ast.If)\n        and isinstance(node.test, ast.UnaryOp)\n        and isinstance(node.test.op, ast.Not)\n        and isinstance(node.test.operand, ast.Name)\n        and node.test.operand.id == "__debug__"\n    )\n\nproduction_asserts = []\nguarded_tests = []\nfor rel in tracked_python_files():\n    source = (ROOT / rel).read_text(encoding="utf-8")\n    tree = ast.parse(source, filename=rel)\n    assertions = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]\n    if Path(rel).name.startswith("test_"):\n        if assertions:\n            require(any(is_optimized_guard(n) for n in tree.body), f"missing optimized-Python test guard: {rel}")\n            require(GUARD_MESSAGE in source, f"missing optimized-Python guard message: {rel}")\n            guarded_tests.append(rel)\n    elif assertions:\n        production_asserts.append((rel, len(assertions)))\nrequire(not production_asserts, f"production runtime asserts remain: {production_asserts}")\nrequire(guarded_tests, "no executable assert-based tests were discovered")\n\nfor rel in guarded_tests:\n    proc = subprocess.run([sys.executable, "-O", str(ROOT / rel)], cwd=ROOT, text=True, capture_output=True)\n    combined = proc.stdout + proc.stderr\n    require(proc.returncode != 0, f"optimized test falsely succeeded: {rel}")\n    require(GUARD_MESSAGE in combined, f"optimized test did not fail via explicit guard: {rel}")\n\nvalid = subprocess.run([sys.executable, "-O", str(BUILDER), "--check"], cwd=ROOT, text=True, capture_output=True)\nrequire(valid.returncode == 0, "valid optimized production execution failed after assert migration")\nbackup = CATALOG.read_bytes()\ntry:\n    with CATALOG.open(encoding="utf-8", newline="") as f:\n        reader = csv.DictReader(f)\n        rows = list(reader)\n        fields = reader.fieldnames\n    matches = [r for r in rows if r["source_id"] == TARGET_SOURCE]\n    require(len(matches) == 1, f"unexpected target-source count: {len(matches)}")\n    matches[0]["sha256"] = "0" * 64\n    out = io.StringIO()\n    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\\n")\n    writer.writeheader()\n    writer.writerows(rows)\n    CATALOG.write_text(out.getvalue(), encoding="utf-8")\n    tampered = subprocess.run([sys.executable, "-O", str(BUILDER), "--check"], cwd=ROOT, text=True, capture_output=True)\n    require(tampered.returncode != 0, "tampered source SHA passed under optimized Python")\n    require("RuntimeError" in tampered.stderr, "tampered optimized failure was not an explicit runtime guard")\nfinally:\n    CATALOG.write_bytes(backup)\nrequire(CATALOG.read_bytes() == backup, "source catalog was not restored after tamper regression")\nprint(f"optimized-Python runtime guards: OK (production asserts=0; guarded tests={len(guarded_tests)}; source tamper rejected)")\n''', encoding="utf-8")


def main():
    production_files = 0
    production_asserts = 0
    test_files = 0
    test_asserts = 0
    for rel in tracked_python_files():
        if rel == "scripts/_issue60_transform.py":
            continue
        if Path(rel).name.startswith("test_"):
            count = guard_test(rel)
            if count:
                test_files += 1
                test_asserts += count
        else:
            count = transform_production(rel)
            if count:
                production_files += 1
                production_asserts += count
    write_regression_test()
    print(
        f"Issue60 transform complete: production={production_files} files/{production_asserts} asserts; "
        f"tests guarded={test_files} files/{test_asserts} asserts"
    )


if __name__ == "__main__":
    main()
