"""Tests for src/littlefs.py."""

import os

from src.littlefs import human_bytes, _resolve_target_dir, stage_copy_files, stage_gzip_files


class TestHumanBytes:
    def test_zero(self):
        assert human_bytes(0) == "0 B"

    def test_bytes(self):
        assert human_bytes(512) == "512 B"

    def test_kilobytes(self):
        assert human_bytes(1024) == "1.00 KB"

    def test_megabytes(self):
        assert human_bytes(1048576) == "1.00 MB"

    def test_fractional(self):
        result = human_bytes(1536)
        assert "KB" in result


class TestResolveTargetDir:
    def test_empty_subdir(self, tmp_path):
        result = _resolve_target_dir(str(tmp_path), "")
        assert result == str(tmp_path)

    def test_nested(self, tmp_path):
        result = _resolve_target_dir(str(tmp_path), "a/b")
        assert result == os.path.join(str(tmp_path), "a", "b")
        assert os.path.isdir(result)

    def test_strips_dotdot(self, tmp_path):
        result = _resolve_target_dir(str(tmp_path), "../evil")
        assert "evil" in result
        assert ".." not in result
        # Should resolve under staging_dir
        assert result.startswith(str(tmp_path))

    def test_strips_dot(self, tmp_path):
        result = _resolve_target_dir(str(tmp_path), "./sub")
        assert result == os.path.join(str(tmp_path), "sub")

    def test_backslash_normalized(self, tmp_path):
        result = _resolve_target_dir(str(tmp_path), "a\\b")
        assert result == os.path.join(str(tmp_path), "a", "b")


class TestStageCopyFiles:
    def test_copies_files(self, tmp_path):
        source_dir = tmp_path / "source_copy"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("hello")
        (source_dir / "file2.txt").write_text("world")

        staging = tmp_path / "staging"
        staging.mkdir()

        count = stage_copy_files(str(source_dir), str(staging))
        assert count == 2
        assert (staging / "file1.txt").exists()
        assert (staging / "file2.txt").exists()

    def test_missing_dir_returns_zero(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        count = stage_copy_files(str(tmp_path / "nonexistent"), str(staging))
        assert count == 0

    def test_with_target_subdir(self, tmp_path):
        source_dir = tmp_path / "source_copy"
        source_dir.mkdir()
        (source_dir / "a.txt").write_text("content")

        staging = tmp_path / "staging"
        staging.mkdir()

        count = stage_copy_files(str(source_dir), str(staging), target_subdir="sub")
        assert count == 1
        assert (staging / "sub" / "a.txt").exists()


class TestStageGzipFiles:
    def test_creates_gzip_files(self, tmp_path):
        source_dir = tmp_path / "source_gzip"
        source_dir.mkdir()
        (source_dir / "index.html").write_text("<html>hello</html>")

        staging = tmp_path / "staging"
        staging.mkdir()

        count = stage_gzip_files(str(source_dir), str(staging))
        assert count == 1
        assert (staging / "index.html.gz").exists()
        assert (staging / "index.html.gz").stat().st_size > 0

    def test_missing_dir_returns_zero(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        count = stage_gzip_files(str(tmp_path / "nonexistent"), str(staging))
        assert count == 0
