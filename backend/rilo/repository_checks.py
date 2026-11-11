"""Read-only static inventory. Pattern matches are observations, not exploit claims."""

from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import PurePosixPath


def analyze(sources: list[dict]) -> dict:
    observations = []
    modules = []
    dependencies: list[dict] = []
    tests = []
    for source in sources:
        path, text = source["reference"], source["content"]
        if "test" in PurePosixPath(path).name.lower():
            tests.append(path)
        if path.endswith(".py"):
            try:
                tree = ast.parse(text)
                imports = sorted(
                    {
                        node.module or ""
                        for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom)
                    }
                    | {
                        alias.name
                        for node in ast.walk(tree)
                        if isinstance(node, ast.Import)
                        for alias in node.names
                    }
                )
                functions = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                routes = []
                for function in functions:
                    for decorator in function.decorator_list:
                        if (
                            isinstance(decorator, ast.Call)
                            and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr
                            in {"get", "post", "put", "patch", "delete", "route"}
                        ):
                            routes.append(
                                {
                                    "function": function.name,
                                    "line": function.lineno,
                                    "method": decorator.func.attr,
                                    "path": decorator.args[0].value
                                    if decorator.args
                                    and isinstance(decorator.args[0], ast.Constant)
                                    else None,
                                }
                            )
                modules.append(
                    {
                        "path": path,
                        "imports": imports,
                        "function_count": len(functions),
                        "routes": routes,
                    }
                )
                for node in ast.walk(tree):
                    rule = None
                    if isinstance(node, ast.Call):
                        name = ast.unparse(node.func)
                        if name in {"eval", "exec"}:
                            rule = "dynamic-code-evaluation"
                        elif name.startswith("subprocess.") and any(
                            k.arg == "shell"
                            and isinstance(k.value, ast.Constant)
                            and k.value.value is True
                            for k in node.keywords
                        ):
                            rule = "shell-true-call"
                        elif (
                            name.endswith(".execute")
                            and node.args
                            and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp))
                        ):
                            rule = "dynamic-sql-expression"
                    if rule and isinstance(node, ast.Call):
                        observations.append(
                            {
                                "rule": rule,
                                "reference": path,
                                "start_line": node.lineno,
                                "end_line": node.end_lineno,
                                "quote": "\n".join(
                                    text.splitlines()[node.lineno - 1 : node.end_lineno]
                                ),
                                "verification": "VERIFIED rule match; exploitability NEEDS MANUAL REVIEW",
                            }
                        )
            except (SyntaxError, RecursionError):
                modules.append({"path": path, "parse_status": "unsupported_or_invalid_syntax"})
        if PurePosixPath(path).name == "package.json":
            try:
                manifest = json.loads(text)
                for field in ("dependencies", "devDependencies"):
                    values = manifest.get(field, {})
                    if isinstance(values, dict):
                        dependencies.extend(
                            {
                                "name": name,
                                "version_spec": version,
                                "ecosystem": "npm",
                                "manifest": path,
                                "vulnerability_status": "not checked",
                            }
                            for name, version in list(values.items())[:300]
                            if isinstance(version, str)
                        )
            except (ValueError, AttributeError):
                observations.append(
                    {
                        "rule": "invalid-dependency-manifest",
                        "reference": path,
                        "verification": "NEEDS MANUAL REVIEW",
                    }
                )
        elif PurePosixPath(path).name == "pyproject.toml":
            try:
                manifest = tomllib.loads(text)
                dependencies.extend(
                    {
                        "requirement": requirement,
                        "ecosystem": "PyPI",
                        "manifest": path,
                        "vulnerability_status": "not checked",
                    }
                    for requirement in manifest.get("project", {}).get("dependencies", [])[:300]
                )
            except (ValueError, AttributeError, TypeError):
                observations.append(
                    {
                        "rule": "invalid-dependency-manifest",
                        "reference": path,
                        "verification": "NEEDS MANUAL REVIEW",
                    }
                )
        for line_number, line in enumerate(text.splitlines(), 1):
            if re.search(r"(?:sk-|ghp_|github_pat_|AKIA)[A-Za-z0-9_\-]{16,}", line):
                observations.append(
                    {
                        "rule": "possible-embedded-credential",
                        "reference": path,
                        "start_line": line_number,
                        "end_line": line_number,
                        "quote": "[credential-like value withheld]",
                        "verification": "NEEDS MANUAL REVIEW; pattern alone cannot confirm a live secret",
                    }
                )
    return {
        "version": "repository-static-v1",
        "modules": modules,
        "observations": observations[:200],
        "dependencies": dependencies[:500],
        "test_files": tests,
        "executed_repository_code": False,
        "limitations": [
            "Static rule matches require contextual review.",
            "Dependency versions are declarations, not installed or resolved versions.",
            "Known vulnerability and outdated-package lookups have not been performed.",
            "Only captured files were inspected.",
        ],
    }
