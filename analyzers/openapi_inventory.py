"""Discover operations declared in local OpenAPI and Swagger documents."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

_MAX_SPEC_BYTES = 10_000_000
_MARKER = re.compile(
    rb'(?m)(?:^|[\r\n{,])\s*(?:openapi|swagger)\s*:|"(?:openapi|swagger)"\s*:',
    re.IGNORECASE,
)
_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _looks_like_spec(path: Path) -> bool:
    if "openapi" in path.name.casefold() or "swagger" in path.name.casefold():
        return True
    with path.open("rb") as source:
        previous = b""
        while chunk := source.read(65_536):
            combined = previous + chunk
            if _MARKER.search(combined):
                return True
            previous = combined[-128:]
    return False


def _path_item(
    item: dict[str, Any],
    document: dict[str, Any],
    source: str,
    path: str,
    warnings: list[str],
    seen: set[str] | None = None,
) -> dict[str, Any]:
    reference = item.get("$ref")
    if reference is None:
        return item
    seen = set() if seen is None else seen
    if (
        not isinstance(reference, str)
        or not reference.startswith("#/")
        or reference in seen
        or len(seen) >= 50
    ):
        warnings.append(f"Unresolved or external path reference for {path} in {source}.")
        return {key: value for key, value in item.items() if key != "$ref"}
    seen.add(reference)
    target: Any = document
    for part in reference[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or part not in target:
            warnings.append(f"Unresolved local path reference for {path} in {source}.")
            return {key: value for key, value in item.items() if key != "$ref"}
        target = target[part]
    if not isinstance(target, dict):
        warnings.append(f"Invalid local path reference for {path} in {source}.")
        return {key: value for key, value in item.items() if key != "$ref"}
    resolved = _path_item(target, document, source, path, warnings, seen)
    siblings = {key: value for key, value in item.items() if key != "$ref"}
    conflicts = {
        key for key in siblings.keys() & resolved.keys()
        if isinstance(key, str) and key.casefold() in _METHODS
    }
    if conflicts:
        warnings.append(f"Conflicting path reference operations for {path} in {source}.")
    return {
        key: value for key, value in {**resolved, **siblings}.items()
        if key not in conflicts
    }


def collect_openapi_inventory(root: Path, files: Iterable[Path]) -> dict[str, list]:
    """Extract local specification operations without resolving remote references."""
    endpoints: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted(files):
        source = path.relative_to(root).as_posix()
        try:
            if not path.resolve().is_relative_to(root):
                warnings.append(f"Skipped API candidate outside the repository: {source}.")
                continue
            if not _looks_like_spec(path):
                continue
            if path.stat().st_size > _MAX_SPEC_BYTES:
                warnings.append(f"API specification exceeds the size limit: {source}.")
                continue
            text = path.read_text(encoding="utf-8-sig")
            document = json.loads(text) if path.suffix.casefold() == ".json" else yaml.safe_load(text)
        except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError, RecursionError) as error:
            warnings.append(f"Could not read or parse API candidate {source}: {type(error).__name__}.")
            continue
        if not isinstance(document, dict):
            if "openapi" in path.name.casefold() or "swagger" in path.name.casefold():
                warnings.append(f"API candidate is not a document mapping: {source}.")
            continue
        if "openapi" in document:
            version = str(document["openapi"])
            specification = f"OpenAPI {version}"
            supported = version.startswith("3.")
        elif "swagger" in document:
            version = str(document["swagger"])
            specification = f"Swagger {version}"
            supported = version == "2.0"
        else:
            if "openapi" in path.name.casefold() or "swagger" in path.name.casefold():
                warnings.append(f"No OpenAPI or Swagger version found in {source}.")
            continue
        if not supported:
            warnings.append(f"Unsupported API specification version in {source}: {specification}.")
            continue
        paths = document.get("paths")
        if not isinstance(paths, dict):
            warnings.append(f"API specification has no paths mapping: {source}.")
            continue
        for route, raw_item in paths.items():
            if not isinstance(route, str) or not route.startswith("/") or not isinstance(raw_item, dict):
                warnings.append(f"Invalid API path declaration in {source}.")
                continue
            item = _path_item(raw_item, document, source, route, warnings)
            for method, operation in item.items():
                if not isinstance(method, str) or method.casefold() not in _METHODS:
                    continue
                if not isinstance(operation, dict):
                    warnings.append(f"Invalid {method.upper()} operation for {route} in {source}.")
                    continue
                if "$ref" in operation:
                    warnings.append(f"Unresolved operation reference for {route} in {source}.")
                endpoint: dict[str, Any] = {
                    "direction": "unknown",
                    "method": method.upper(),
                    "path": route,
                    "source": source,
                    "specification": specification,
                }
                for key in ("operationId", "summary"):
                    if isinstance(operation.get(key), str):
                        endpoint["operation_id" if key == "operationId" else key] = operation[key]
                endpoints.append(endpoint)
    return {"endpoints": endpoints, "warnings": warnings}
