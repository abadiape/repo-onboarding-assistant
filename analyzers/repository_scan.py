"""Repository scan."""
# Explicit aliases preserve the original import paths.
# ruff: noqa: PLC0414
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from analyzers.analyzers import DEFAULT_ANALYZERS, Analyzer, enrich_repository_model
from analyzers.api_inventory import collect_api_inventory
from analyzers.scan_dependencies import (
    _collect_dependencies,
    _collect_locked_dependencies,
)
from analyzers.scan_files import EXTENSION_TO_LANGUAGE as EXTENSION_TO_LANGUAGE
from analyzers.scan_files import IGNORED_DIRS as IGNORED_DIRS
from analyzers.scan_files import (
    _collect_directories,
    _collect_repository_files,
    _iter_project_files,
)
from analyzers.scan_io import _read_json
from analyzers.scan_onboarding import CI_CD_PATTERNS as CI_CD_PATTERNS
from analyzers.scan_onboarding import IMPORTANT_FILENAMES as IMPORTANT_FILENAMES
from analyzers.scan_onboarding import SETUP_GUIDE_FILENAMES as SETUP_GUIDE_FILENAMES
from analyzers.scan_onboarding import (
    _collect_ci_cd_files,
    _collect_ci_commands,
    _collect_entry_points,
    _collect_important_files,
    _collect_onboarding_docs,
    _detect_patterns,
    _extract_documented_setup_commands,
    _extract_readme_summary,
)
from analyzers.scan_tooling import (
    _build_instructions,
    _detect_build_tools,
    _detect_languages,
    _detect_package_managers,
    _detect_test_frameworks,
    _test_instructions,
)
from models.models import RepositoryModel


def scan_repository(
    repo_path: str | Path,
    analyzers: Sequence[Analyzer] = DEFAULT_ANALYZERS,
) -> RepositoryModel:
    """Scan a repository directory and return its normalized model.

    Raises:
        FileNotFoundError: if repo_path does not exist.
        NotADirectoryError: if repo_path is not a directory.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    files_by_name: dict[str, list[Path]] = {}
    for file_path in _iter_project_files(root):
        files_by_name.setdefault(file_path.name, []).append(file_path)

    package_json: dict = {}
    if "package.json" in files_by_name:
        package_json = _read_json(files_by_name["package.json"][0])

    languages = _detect_languages(root, files_by_name)
    onboarding_docs, setup_guides = _collect_onboarding_docs(root, files_by_name)
    documented_setup_commands = _extract_documented_setup_commands(
        root, onboarding_docs
    )

    directories = _collect_directories(root)
    top_level_directories = [
        path for path in directories if len(Path(path).parts) == 1
    ]

    ci_cd_files = _collect_ci_cd_files(root, files_by_name)
    build_instructions = _build_instructions(root, files_by_name, package_json)
    test_instructions = _test_instructions(package_json, files_by_name)
    readme_summary = _extract_readme_summary(root, files_by_name)

    model = RepositoryModel(
        repository_name=root.name,
        metadata={
            "name": root.name,
            "root_path": str(root),
            "readme_summary": readme_summary,
        },
        root_path=str(root),
        readme_summary=readme_summary,
        languages=languages,
        dependencies=_collect_dependencies(root, files_by_name),
        locked_dependencies=_collect_locked_dependencies(root, files_by_name),
        directories=directories,
        files=_collect_repository_files(root, files_by_name, ci_cd_files),
        detected_patterns=_detect_patterns(files_by_name, ci_cd_files),
        package_managers=_detect_package_managers(files_by_name),
        build_tools=_detect_build_tools(files_by_name),
        test_frameworks=_detect_test_frameworks(root, files_by_name, package_json),
        important_files=_collect_important_files(root, files_by_name),
        onboarding_docs=onboarding_docs,
        setup_guides=setup_guides,
        documented_setup_commands=documented_setup_commands,
        ci_cd_files=ci_cd_files,
        ci_commands=_collect_ci_commands(root, ci_cd_files),
        top_level_directories=top_level_directories,
        entry_points=_collect_entry_points(root, files_by_name),
        build_instructions=build_instructions,
        test_instructions=test_instructions,
        api_inventory=collect_api_inventory(root, files_by_name.get("webapi.xml", [])),
    )
    return enrich_repository_model(model, analyzers)
