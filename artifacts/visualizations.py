"""Mermaid renderers for repository architecture artifacts.

These renderers consume only RepositoryModel and do not perform repository
scanning or infer source-level relationships.
"""
from __future__ import annotations

from models.models import RepositoryModel


def _label(value: str) -> str:
    """Escape text for use inside a quoted Mermaid label."""
    return (
        str(value)
        .replace("&", "#amp;")
        .replace('"', "#quot;")
        .replace("|", "#124;")
        .replace("<", "#lt;")
        .replace(">", "#gt;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part and part != "."]


def render_dependency_graph_mermaid(model: RepositoryModel) -> str:
    """Render repository dependency declarations as a Mermaid flowchart."""
    lines = [
        "flowchart LR",
        f'    repository["Repository: {_label(model.repository_name)}"]',
    ]
    if not model.dependencies:
        lines += [
            '    none["No declared dependencies"]',
            "    repository --> none",
        ]
    else:
        for index, dependency in enumerate(model.dependencies):
            details = [dependency.name]
            if dependency.version:
                details.append(dependency.version)
            lines.append(f'    dependency_{index}["{_label(" ".join(details))}"]')
            edge_details = [dependency.scope]
            if dependency.source:
                edge_details.append(dependency.source)
            lines.append(
                f'    repository -->|{_label(" · ".join(edge_details))}| '
                f"dependency_{index}"
            )
    return "\n".join(lines) + "\n"


def render_module_graph_mermaid(model: RepositoryModel) -> str:
    """Render directory/file containment from the model's normalized paths."""
    directory_paths = {
        "/".join(_path_parts(path))
        for path in model.directories
        if _path_parts(path)
    }
    file_paths = {
        "/".join(_path_parts(file.path)): file
        for file in model.files
        if _path_parts(file.path)
    }

    # Include missing intermediate directories so every known file has a
    # visible containment path, even for hand-built or partial models.
    for path in file_paths:
        parts = _path_parts(path)
        directory_paths.update(
            "/".join(parts[:index]) for index in range(1, len(parts))
        )

    sorted_directories = sorted(directory_paths)
    sorted_files = sorted(file_paths)
    directory_ids = {
        path: f"directory_{index}"
        for index, path in enumerate(sorted_directories)
    }
    file_ids = {
        path: f"file_{index}"
        for index, path in enumerate(sorted_files)
    }
    lines = [
        "flowchart TD",
        f'    repository["Repository: {_label(model.repository_name)}"]',
    ]

    for path in sorted_directories:
        lines.append(
            f'    {directory_ids[path]}["{_label(path + "/")}"]'
        )
        parent = path.rpartition("/")[0]
        parent_id = directory_ids.get(parent, "repository")
        lines.append(f"    {parent_id} --> {directory_ids[path]}")

    for path in sorted_files:
        file_record = file_paths[path]
        details = [path]
        if file_record.kind:
            details.append(file_record.kind)
        if file_record.language:
            details.append(file_record.language)
        lines.append(
            f'    {file_ids[path]}["{_label(" · ".join(details))}"]'
        )
        parent = path.rpartition("/")[0]
        parent_id = directory_ids.get(parent, "repository")
        lines.append(f"    {parent_id} --> {file_ids[path]}")

    if not sorted_directories and not sorted_files:
        lines += [
            '    empty["No directories or files recorded"]',
            "    repository --> empty",
        ]
    return "\n".join(lines) + "\n"


def render_architecture_overview_mermaid(model: RepositoryModel) -> str:
    """Render a high-level view of facts explicitly represented by the model."""
    lines = [
        "flowchart TD",
        f'    repository["Repository: {_label(model.repository_name)}"]',
    ]
    groups = (
        ("technologies", "Technologies", [
            *(f"Language: {value}" for value in model.languages),
            *(f"Framework: {value}" for value in model.frameworks),
        ]),
        ("areas", "Top-level areas", list(model.top_level_directories)),
        ("entry_points", "Entry points", list(model.entry_points)),
        (
            "dependencies",
            "Declared dependencies",
            [
                f"{item.name}" + (f" {item.version}" if item.version else "")
                for item in model.dependencies
            ],
        ),
        ("patterns", "Detected patterns", list(model.detected_patterns)),
    )

    for group_id, title, values in groups:
        if not values:
            continue
        lines.append(f'    {group_id}["{title}"]')
        lines.append(f"    repository --> {group_id}")
        for index, value in enumerate(values):
            node_id = f"{group_id}_{index}"
            lines.append(f'    {node_id}["{_label(value)}"]')
            lines.append(f"    {group_id} --> {node_id}")

    if len(lines) == 2:
        lines += [
            '    empty["No architecture facts detected"]',
            "    repository --> empty",
        ]
    return "\n".join(lines) + "\n"
