"""End-to-end test: run_onboarding produces 4 artifacts + valid SkillResult."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from onboarding_skill import run_onboarding


def test_run_onboarding_end_to_end(tmp_path):
    repo = tmp_path / "sample"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    (repo / "package.json").write_text('{"scripts": {"build": "tsc", "test": "jest"}}',
                                       encoding="utf-8")
    (repo / "tsconfig.json").write_text("{}", encoding="utf-8")
    (repo / "src" / "index.ts").write_text("console.log(1)\n", encoding="utf-8")

    out = tmp_path / "outputs"
    result = run_onboarding(repo, out)

    assert result.summary == "Repository onboarding analysis completed"
    assert len(result.artifacts) == 4
    for expected in ("summary.md", "learning_path.md", "repository_map.json", "manifest.json"):
        assert (out / expected).is_file(), f"missing {expected}"

    repo_map = json.loads((out / "repository_map.json").read_text(encoding="utf-8"))
    assert repo_map["repository_name"] == "sample"
    assert "TypeScript" in repo_map["languages"]

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "generated_at" in manifest
    assert len(manifest["artifacts"]) == 4
