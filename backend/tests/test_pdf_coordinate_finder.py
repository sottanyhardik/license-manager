from __future__ import annotations

from pathlib import Path

import pytest

from apps.allotment.scripts.pdf_coordinate_finder import (
    create_coordinate_grid,
    main,
    parse_args,
)


def test_create_coordinate_grid_writes_pdf(tmp_path: Path) -> None:
    output_path = tmp_path / "grid.pdf"

    created_path = create_coordinate_grid(output_path, grid_spacing=100)

    assert created_path == output_path
    assert output_path.read_bytes().startswith(b"%PDF")


def test_create_coordinate_grid_rejects_existing_output_without_overwrite(tmp_path: Path) -> None:
    output_path = tmp_path / "grid.pdf"
    output_path.write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="already exists"):
        create_coordinate_grid(output_path)

    assert output_path.read_bytes() == b"existing"


def test_create_coordinate_grid_rejects_directory_output(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError, match="is a directory"):
        create_coordinate_grid(tmp_path)


def test_create_coordinate_grid_allows_explicit_overwrite(tmp_path: Path) -> None:
    output_path = tmp_path / "grid.pdf"
    output_path.write_bytes(b"existing")

    create_coordinate_grid(output_path, overwrite=True)

    assert output_path.read_bytes().startswith(b"%PDF")


def test_create_coordinate_grid_rejects_invalid_grid_spacing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        create_coordinate_grid(tmp_path / "grid.pdf", grid_spacing=0)


def test_parse_args_rejects_non_positive_grid_spacing() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["grid.pdf", "--grid-spacing", "-1"])

    assert exc_info.value.code == 2


def test_main_generates_pdf_with_overwrite_flag(tmp_path: Path) -> None:
    output_path = tmp_path / "grid.pdf"
    output_path.write_bytes(b"existing")

    exit_code = main([str(output_path), "--grid-spacing", "75", "--overwrite"])

    assert exit_code == 0
    assert output_path.read_bytes().startswith(b"%PDF")
