"""Tests for bridge.py — Docker invocation paths."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from bambox.bridge import (
    DOCKER_IMAGE,
    _run_bridge_docker,
    _run_bridge_docker_copy,
)

# -- _run_bridge_docker --------------------------------------------------------


class TestRunBridgeDocker:
    def test_docker_not_installed(self):
        """FileNotFoundError from 'docker info' should raise with install hint."""
        with patch("bambox.bridge.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="Docker is not installed"):
                _run_bridge_docker(["-c", "/tmp/token.json", "status", "DEV1"])

    def test_docker_not_running(self):
        """Non-zero 'docker info' should raise with install hint."""
        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1, "", "error")
            with pytest.raises(RuntimeError, match="Docker is not running"):
                _run_bridge_docker(["-c", "/tmp/token.json", "status", "DEV1"])

    def test_bind_mount_basic_args(self):
        """Non-file args should be passed through without -v mounts."""
        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 0, '{"result":"ok"}', ""),  # docker run
            ]
            result = _run_bridge_docker(["-c", "/tmp/token.json", "status", "DEV1"])

            docker_run_call = mock_run.call_args_list[2]
            cmd = docker_run_call[0][0]
            assert cmd[0] == "docker"
            assert cmd[1] == "run"
            assert "--rm" in cmd
            assert "--platform" in cmd
            assert DOCKER_IMAGE in cmd
            assert result.returncode == 0

    def test_args_passed_through(self):
        """Args in Rust format should be passed through to the container."""
        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 0, '{"result":"ok"}', ""),  # docker run
            ]
            _run_bridge_docker(["-c", "/tmp/token.json", "status", "DEV1"])

            docker_run_call = mock_run.call_args_list[2]
            cmd = docker_run_call[0][0]
            image_idx = cmd.index(DOCKER_IMAGE)
            bridge_args = cmd[image_idx + 1 :]
            assert bridge_args[0] == "-c"
            assert bridge_args[1] == "/tmp/token.json"
            assert bridge_args[2] == "status"
            assert bridge_args[3] == "DEV1"

    def test_bind_mount_file_args(self, tmp_path):
        """Existing file paths should be volume-mounted."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake 3mf")
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")

        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 0, '{"result":"ok"}', ""),  # docker run
            ]
            _run_bridge_docker(["-c", str(token_file), "print", str(test_file), "DEV1"])

            docker_run_call = mock_run.call_args_list[2]
            cmd = docker_run_call[0][0]
            v_indices = [i for i, c in enumerate(cmd) if c == "-v"]
            assert len(v_indices) >= 2
            mounts = [cmd[i + 1] for i in v_indices]
            assert any(":ro" in m and "/input/" in m for m in mounts)

    def test_verbose_flag_appended(self):
        """verbose=True should add -v to Docker run command."""
        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 0, '{"result":"ok"}', ""),  # docker run
            ]
            _run_bridge_docker(["status", "DEV1"], verbose=True)

            cmd = mock_run.call_args_list[2][0][0]
            image_idx = cmd.index(DOCKER_IMAGE)
            tail = cmd[image_idx + 1 :]
            assert "-v" in tail

    def test_docker_image_is_rust_bridge(self):
        """DOCKER_IMAGE should point to the Rust bambox-bridge image."""
        assert DOCKER_IMAGE == "estampo/bambox-bridge:bambu-02.05.00.00"

    def test_bind_mount_failure_triggers_copy_fallback(self, tmp_path):
        """'cannot read' in stderr should trigger COPY fallback."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake 3mf")

        with (
            patch("bambox.bridge.subprocess.run") as mock_run,
            patch("bambox.bridge._run_bridge_docker_copy") as mock_copy,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess(
                    [], 1, "", "cannot read /input/test.3mf: Is a directory"
                ),
            ]
            mock_copy.return_value = subprocess.CompletedProcess([], 0, '{"result":"ok"}', "")

            _run_bridge_docker(["-c", str(test_file), "print", str(test_file), "DEV1"])
            mock_copy.assert_called_once()

    def test_non_read_error_returns_without_fallback(self, tmp_path):
        """Errors that aren't 'cannot read' should NOT trigger fallback."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake 3mf")

        with (
            patch("bambox.bridge.subprocess.run") as mock_run,
            patch("bambox.bridge._run_bridge_docker_copy") as mock_copy,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 1, "", "some other error"),
            ]
            result = _run_bridge_docker(["-c", str(test_file), "print", str(test_file), "DEV1"])
            mock_copy.assert_not_called()
            assert result.returncode == 1

    def test_no_file_args_skips_fallback(self):
        """Failure without file args should NOT attempt fallback."""
        with (
            patch("bambox.bridge.subprocess.run") as mock_run,
            patch("bambox.bridge._run_bridge_docker_copy") as mock_copy,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker info
                subprocess.CompletedProcess([], 0, "", ""),  # docker pull
                subprocess.CompletedProcess([], 1, "", "cannot read something"),
            ]
            result = _run_bridge_docker(["status", "DEV1"])
            mock_copy.assert_not_called()
            assert result.returncode == 1


# -- _run_bridge_docker_copy ---------------------------------------------------


class TestRunBridgeDockerCopy:
    def test_builds_and_runs_temp_image(self, tmp_path):
        """Should build a temp Docker image, run it, then clean up."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake 3mf content")
        real_path = str(test_file.resolve())

        file_args = {real_path: "/input/test.3mf"}

        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0, "", ""),  # docker build
                subprocess.CompletedProcess([], 0, '{"result":"ok"}', ""),  # docker run
                subprocess.CompletedProcess([], 0, "", ""),  # docker rmi
            ]
            result = _run_bridge_docker_copy(
                ["-c", "/tmp/token.json", "print", str(test_file), "DEV1"],
                file_args,
            )

            assert result.returncode == 0
            build_cmd = mock_run.call_args_list[0][0][0]
            assert build_cmd[:3] == ["docker", "build", "-t"]

            run_cmd = mock_run.call_args_list[1][0][0]
            assert run_cmd[0:2] == ["docker", "run"]
            assert "/input/test.3mf" in run_cmd

            rmi_call = mock_run.call_args_list[2]
            assert "rmi" in rmi_call[0][0]

    def test_build_failure_raises(self, tmp_path):
        """Failed docker build should raise RuntimeError."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake")
        real_path = str(test_file.resolve())
        file_args = {real_path: "/input/test.3mf"}

        with patch("bambox.bridge.subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 1, "", "build error"),  # docker build
                subprocess.CompletedProcess([], 0, "", ""),  # docker rmi
            ]
            with pytest.raises(RuntimeError, match="Docker build failed"):
                _run_bridge_docker_copy(
                    ["-c", "/tmp/token.json", "print", str(test_file)], file_args
                )

    def test_dockerfile_contents(self, tmp_path):
        """Generated Dockerfile should COPY files from base image."""
        test_file = tmp_path / "test.3mf"
        test_file.write_text("fake")
        real_path = str(test_file.resolve())
        file_args = {real_path: "/input/test.3mf"}

        dockerfiles_written: list[str] = []

        def capture_dockerfile(cmd, **kwargs):
            cwd = kwargs.get("cwd", "")
            if cwd and cmd[:2] == ["docker", "build"]:
                df = Path(cwd) / "Dockerfile"
                if df.exists():
                    dockerfiles_written.append(df.read_text())
            return subprocess.CompletedProcess([], 0, "", "")

        with patch("bambox.bridge.subprocess.run", side_effect=capture_dockerfile):
            _run_bridge_docker_copy(["-c", "/tmp/token.json", "print", str(test_file)], file_args)

        assert len(dockerfiles_written) == 1
        df = dockerfiles_written[0]
        assert df.startswith(f"FROM {DOCKER_IMAGE}")
        assert "COPY test.3mf /input/test.3mf" in df
