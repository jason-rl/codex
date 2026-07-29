#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
MANUAL_TRIGGERS = {"workflow_call", "workflow_dispatch"}


def workflow_triggers(path: Path) -> set[str]:
    lines = path.read_text().splitlines()
    try:
        on_line = next(index for index, line in enumerate(lines) if line == "on:")
    except StopIteration as error:
        raise AssertionError(f"{path.name} does not contain a top-level on mapping") from error

    triggers = set()
    for line in lines[on_line + 1 :]:
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([a-z_]+):", line)
        if match:
            triggers.add(match.group(1))
    return triggers


def workflow_on_mapping(path: Path) -> str:
    lines = path.read_text().splitlines()
    on_line = lines.index("on:")
    end_line = next(
        (
            index
            for index, line in enumerate(lines[on_line + 1 :], start=on_line + 1)
            if line and not line.startswith(" ")
        ),
        len(lines),
    )
    return "\n".join(lines[on_line:end_line])


class ForkWorkflowPolicyTest(unittest.TestCase):
    def test_only_fork_rust_release_runs_automatically(self) -> None:
        violations = []
        for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
            triggers = workflow_triggers(path)
            automatic_triggers = triggers - MANUAL_TRIGGERS
            if path.name == "fork-rust-release.yml":
                if triggers != {"push"}:
                    violations.append(
                        f"{path.name}: expected only push, found {sorted(triggers)}"
                    )
            elif path.name == "rust-release.yml":
                if triggers != {"workflow_dispatch"}:
                    violations.append(
                        f"{path.name}: expected only workflow_dispatch, "
                        f"found {sorted(triggers)}"
                    )
            elif automatic_triggers:
                violations.append(
                    f"{path.name}: automatic triggers {sorted(automatic_triggers)}"
                )

        self.assertEqual([], violations)

    def test_fork_rust_release_only_runs_for_main(self) -> None:
        path = WORKFLOWS_DIR / "fork-rust-release.yml"
        self.assertTrue(path.is_file())
        on_block = workflow_on_mapping(path)
        self.assertIn("  push:\n    branches: [main]", on_block)
        self.assertNotIn("    tags:", on_block)

    def test_fork_rust_release_is_upstream_shaped_arm64_macos_pipeline(
        self,
    ) -> None:
        path = WORKFLOWS_DIR / "fork-rust-release.yml"
        self.assertTrue(path.is_file())
        release_workflow = path.read_text()
        required_fragments = [
            "runner: macos-26",
            "timeout-minutes: 180",
            "target: aarch64-apple-darwin",
            "bundle: primary",
            'binaries: "codex codex-code-mode-host"',
            'MACOSX_DEPLOYMENT_TARGET: "26.3"',
            'CARGO_BUILD_JOBS: "2"',
            "CARGO_PROFILE_RELEASE_LTO: thin",
            'RUSTFLAGS: "-C target-cpu=apple-m4"',
            "Swatinem/rust-cache@e18b497796c12c097a38f9edb9d0641fb99eee32",
            "workspaces: codex-rs -> target",
            "cache-targets: false",
            "Mozilla-Actions/sccache-action@fc920bf0ec8de6ee65d409111f7ec508035751ba",
            "continue-on-error: true",
            "if: steps.sccache.outcome == 'success'",
            'RUSTC_WRAPPER=sccache',
            'SCCACHE_GHA_ENABLED: "true"',
            'SCCACHE_CLIENT_SIDE: "1"',
            'SCCACHE_IDLE_TIMEOUT: "0"',
            'SCCACHE_ERROR_LOG=${RUNNER_TEMP}/sccache-error.log',
            "SCCACHE_LOG: warn",
            'memory_log="${RUNNER_TEMP}/cargo-build-memory.log"',
            'sccache --show-stats',
            "name: rust-release-build-diagnostics-${{ matrix.target }}-${{ matrix.bundle }}",
            '${{ runner.temp }}/cargo-build-memory.log',
            '${{ runner.temp }}/sccache-error.log',
            "archive-release-symbols-and-strip-binaries.sh",
            "cargo-timings-rust-release-${{ matrix.target }}-${{ matrix.bundle }}",
            'release_dir="${RUNNER_TEMP}/codex-release-${TARGET}"',
            'rm -rf "target/${TARGET}"',
            'rm -rf "${RUNNER_TEMP}/codex-symbols-${{ matrix.artifact_name }}"',
            'rm -rf "${RUNNER_TEMP}/rusty_v8"',
            'rm -rf "$CARGO_HOME/registry/src"',
            'rm -rf "$release_dir" "$package_dir"',
            'rm -rf "$pkg_root"',
            "name: ${{ matrix.artifact_name }}-release-inputs",
            "compression-level: 0",
            "  package:",
            "needs: build",
            "timeout-minutes: 30",
            "name: aarch64-apple-darwin-release-inputs",
            "path: codex-rs/target/aarch64-apple-darwin/release",
            'chmod 0755 "${release_dir}/${binary}"',
            'pkg_size_kib="$(du -sk "$pkg_path"',
            'dmg_size_kib="$((pkg_size_kib + 65536))"',
            'ln "$pkg_path" "${dmg_root}/Install Codex.pkg"',
            '-srcfolder "$dmg_root"',
            "-format UDZO",
            'hdiutil verify "${dist_dir}/codex-${TARGET}.dmg"',
            'rustc --print target-cpus',
            '--target "$target"',
            'build-codex-package-archive.sh',
            'codex-package-aarch64-apple-darwin.tar.gz',
            'codex-package-aarch64-apple-darwin.tar.zst',
            'codex-package_SHA256SUMS',
            'com.github.jason-rl.codex',
            'Install Codex.pkg',
            "needs: package",
            'config-schema.json',
            'install.sh',
            'install.ps1',
            "runs-on: ubuntu-slim",
        ]
        missing = [
            fragment for fragment in required_fragments if fragment not in release_workflow
        ]
        self.assertEqual([], missing)
        self.assertEqual(2, release_workflow.count("      - parallel:\n"))

        forbidden_fragments = [
            "codesign",
            "azure",
            "x86_64-apple-darwin",
            "unknown-linux",
            "pc-windows",
            "npm",
            "winget",
            "dot-slash",
            "r2-release",
            "releases.openai.com",
            "ubuntu-latest",
            "codex-responses-api-proxy",
            'cp "$pkg_path" "${dmg_root}/Install Codex.pkg"',
            "-format UDRW",
            'hdiutil attach "$writable_dmg"',
            "hdiutil convert",
            '${GITHUB_WORKSPACE}/.github/workflows:${PATH}',
        ]
        present = [
            fragment
            for fragment in forbidden_fragments
            if fragment in release_workflow.lower()
        ]
        self.assertEqual([], present)

    def test_fork_rust_release_local_references_exist(self) -> None:
        path = WORKFLOWS_DIR / "fork-rust-release.yml"
        self.assertTrue(path.is_file())
        release_workflow = path.read_text()
        references = {
            match.removeprefix("./")
            for match in re.findall(r"uses:\s+(\./[^\s]+)", release_workflow)
        }
        references.update(
            re.findall(r"\$\{GITHUB_WORKSPACE\}/([^\"'\s]+)", release_workflow)
        )
        missing = [
            reference
            for reference in sorted(references)
            if not (REPO_ROOT / reference).exists()
        ]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
