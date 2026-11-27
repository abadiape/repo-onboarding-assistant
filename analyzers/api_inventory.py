"""Collect project-owned Magento Web API declarations without executing the application."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _contract(module: Path, service: str, method: str, root: Path) -> dict:
    parts = service.lstrip("\\").split("\\")
    if len(parts) < 3 or parts[:2] != [module.parent.name, module.name]:
        return {}
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts):
        return {}
    path = module.joinpath(*parts[2:]).with_suffix(".php")
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return {"contract_warning": f"Could not read {path.relative_to(root).as_posix()}: {error}"}
    result: dict = {"contract_source": path.relative_to(root).as_posix()}
    match = re.search(
        r"(?P<doc>/\*\*(?:(?!/\*\*|\*/)[\s\S])*?\*/\s*)?"
        r"(?:public\s+)?function\s+" + re.escape(method) + r"\s*\((?P<args>[^()]*)\)",
        text,
    )
    if not match:
        return result
    doc = match.group("doc") or ""
    types = {name: kind for kind, name in re.findall(r"@param\s+(\S+)\s+\$(\w+)", doc)}
    result["parameters"] = [
        {"name": name, "type": types.get(name, ""), "optional": "=" in argument}
        for argument in match.group("args").split(",")
        if (name_match := re.search(r"\$(\w+)", argument))
        for name in [name_match.group(1)]
    ]
    return_type = re.search(r"@return\s+(\S+)", doc)
    if return_type:
        result["return_type"] = return_type.group(1)
    return result


def collect_api_inventory(root: Path, files: list[Path]) -> dict:
    """Return declarations and parse warnings; do not infer deployed routes."""
    endpoints: list[dict] = []
    warnings: list[str] = []
    for path in sorted(files):
        relative = path.relative_to(root)
        parts = relative.parts
        if len(parts) != 6 or parts[:2] != ("app", "code") or parts[4:] != ("etc", "webapi.xml"):
            continue
        source = relative.as_posix()
        try:
            routes = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as error:
            warnings.append(f"Could not parse {source}: {error}")
            continue
        module = path.parent.parent
        for route in routes.findall("route"):
            url, method = route.get("url", ""), route.get("method", "")
            if not url or not method:
                warnings.append(f"Route missing URL or method in {source}")
                continue
            service = route.find("service")
            service_class = service.get("class", "") if service is not None else ""
            service_method = service.get("method", "") if service is not None else ""
            contract = _contract(module, service_class, service_method, root) if service_class and service_method else {}
            warning = contract.pop("contract_warning", "")
            if warning:
                warnings.append(warning)
            endpoints.append({
                "direction": "incoming",
                "method": method.upper(),
                "path": url,
                "module": f"{parts[2]}_{parts[3]}",
                "source": source,
                "service": service_class,
                "service_method": service_method,
                "resources": [item.get("ref", "") for item in route.findall("./resources/resource") if item.get("ref")],
                "forced_parameters": [item.get("name", "") for item in route.findall("./data/parameter") if item.get("name")],
                **contract,
            })
    return {"endpoints": endpoints, "warnings": warnings}
