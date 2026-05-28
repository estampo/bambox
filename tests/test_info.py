"""Tests for bambox.info — reading metadata from .gcode.3mf archives."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from shared_fixtures import (
    MINIMAL_GCODE,
    MINIMAL_SLICE_INFO,
    build_valid_3mf,
)

from bambox.info import (
    Filament,
    PrintInfo,
    extract_print_info,
    extract_print_info_buffer,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "e2e_cura_p1s"
REFERENCE_3MF = FIXTURE_DIR / "reference.gcode.3mf"


class TestPackageReexport:
    def test_public_api_importable_from_package(self) -> None:
        import bambox

        assert bambox.extract_print_info is extract_print_info
        assert bambox.extract_print_info_buffer is extract_print_info_buffer
        assert bambox.PrintInfo is PrintInfo
        assert bambox.Filament is Filament


class TestPrintInfoDefaults:
    def test_empty_defaults(self) -> None:
        p = PrintInfo()
        assert p.time_seconds == 0
        assert p.weight_g == 0.0
        assert p.layers == 0
        assert p.bed_type is None
        assert p.printer_model_id == ""
        assert p.filaments == []

    def test_to_dict_json_serializable(self) -> None:
        p = PrintInfo(
            time_seconds=150,
            weight_g=5.0,
            layers=3,
            bed_type="Textured PEI Plate",
            printer_model_id="C12",
            filaments=[
                Filament(
                    id=1,
                    type="PLA",
                    color="F2754E",
                    used_m=1.0,
                    used_g=3.0,
                    tray_info_idx="GFL99",
                )
            ],
        )
        # Must not raise
        d = p.to_dict()
        json.dumps(d)
        assert d["time_seconds"] == 150
        assert d["weight_g"] == 5.0
        assert d["bed_type"] == "Textured PEI Plate"
        assert d["filaments"][0]["id"] == 1
        assert d["filaments"][0]["color"] == "F2754E"


class TestMinimalArchive:
    def test_reads_minimal_fixture(self, tmp_path: Path) -> None:
        path = build_valid_3mf(tmp_path)
        info = extract_print_info(path)
        assert info.time_seconds == 150
        assert info.weight_g == 5.0
        assert info.layers == 3
        assert info.printer_model_id == "C12"
        assert len(info.filaments) == 1
        f = info.filaments[0]
        assert f.id == 1
        assert f.type == "PLA"
        assert f.color == "F2754E"  # leading '#' stripped, uppercased
        assert f.used_m == 1.0
        assert f.used_g == 3.0
        assert f.tray_info_idx == "GFL99"

    def test_bed_type_present_when_set(self, tmp_path: Path) -> None:
        settings = json.dumps({"curr_bed_type": "Textured PEI Plate"})
        path = build_valid_3mf(tmp_path, settings=settings)
        info = extract_print_info(path)
        assert info.bed_type == "Textured PEI Plate"

    def test_bed_type_absent_when_unset(self, tmp_path: Path) -> None:
        path = build_valid_3mf(tmp_path)  # MINIMAL_SETTINGS has no curr_bed_type
        info = extract_print_info(path)
        assert info.bed_type is None

    def test_buffer_api(self, tmp_path: Path) -> None:
        path = build_valid_3mf(tmp_path)
        with open(path, "rb") as fh:
            info = extract_print_info_buffer(fh)
        assert info.layers == 3


class TestMultiFilament:
    def test_two_filaments(self, tmp_path: Path) -> None:
        slice_info = MINIMAL_SLICE_INFO.replace(
            '<filament id="1" tray_info_idx="GFL99" type="PLA" color="#F2754E" '
            'used_m="1.00" used_g="3.00" />',
            (
                '<filament id="1" tray_info_idx="GFL99" type="PLA" color="#F2754E" '
                'used_m="1.00" used_g="3.00" />'
                '<filament id="2" tray_info_idx="GFL00" type="PETG-CF" color="#2850E0" '
                'used_m="2.50" used_g="7.20" />'
            ),
        )
        path = build_valid_3mf(tmp_path, slice_info=slice_info)
        info = extract_print_info(path)
        assert [f.id for f in info.filaments] == [1, 2]
        assert info.filaments[1].type == "PETG-CF"
        assert info.filaments[1].color == "2850E0"
        assert info.filaments[1].used_g == 7.20
        assert info.filaments[0].tray_info_idx == "GFL99"
        assert info.filaments[1].tray_info_idx == "GFL00"


class TestRobustness:
    def test_bad_zip_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "broken.3mf"
        bad.write_bytes(b"not a zip")
        with pytest.raises(zipfile.BadZipFile):
            extract_print_info(bad)

    def test_missing_slice_info_returns_defaults(self, tmp_path: Path) -> None:
        out = tmp_path / "no_slice.3mf"
        with zipfile.ZipFile(out, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("Metadata/plate_1.gcode", MINIMAL_GCODE.encode())
        info = extract_print_info(out)
        assert info.time_seconds == 0
        assert info.filaments == []
        assert info.layers == 3  # gcode header still parseable

    def test_malformed_xml_does_not_raise(self, tmp_path: Path) -> None:
        path = build_valid_3mf(tmp_path, slice_info="not xml at all")
        info = extract_print_info(path)
        assert info.time_seconds == 0
        assert info.filaments == []

    def test_malformed_settings_json_does_not_raise(self, tmp_path: Path) -> None:
        path = build_valid_3mf(tmp_path, settings="{ not json")
        info = extract_print_info(path)
        assert info.bed_type is None

    def test_filament_with_missing_id_is_included(self, tmp_path: Path) -> None:
        # A <filament> without a usable id is still reported (id defaults to 0),
        # matching the historical validate._extract_3mf_metadata behavior.
        slice_info = MINIMAL_SLICE_INFO.replace(
            '<filament id="1" tray_info_idx="GFL99" type="PLA"',
            '<filament tray_info_idx="GFL99" type="PLA"',
        )
        path = build_valid_3mf(tmp_path, slice_info=slice_info)
        info = extract_print_info(path)
        assert [f.type for f in info.filaments] == ["PLA"]
        assert info.filaments[0].id == 0

    def test_non_numeric_metadata_does_not_raise(self, tmp_path: Path) -> None:
        slice_info = MINIMAL_SLICE_INFO.replace(
            'key="prediction" value="150"', 'key="prediction" value="oops"'
        ).replace('key="weight" value="5.00"', 'key="weight" value="-"')
        path = build_valid_3mf(tmp_path, slice_info=slice_info)
        info = extract_print_info(path)
        assert info.time_seconds == 0
        assert info.weight_g == 0.0


class TestReferenceArchive:
    @pytest.mark.skipif(not REFERENCE_3MF.exists(), reason="reference fixture not available")
    def test_reference_extracts_cleanly(self) -> None:
        info = extract_print_info(REFERENCE_3MF)
        assert info.time_seconds > 0
        assert info.weight_g > 0
        assert info.layers > 0
        assert info.printer_model_id  # non-empty
        assert len(info.filaments) >= 1
        for f in info.filaments:
            assert f.id >= 1
            assert f.type  # non-empty
            # color may be empty if archive omits it, but if set must be hex w/o '#'
            assert not f.color.startswith("#")
