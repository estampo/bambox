"""Tests for CuraEngine printer definitions and BAMBOX header parsing."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from bambox.cli import _assign_filament_slots, _parse_filament_args, main
from bambox.cura import (
    available_cura_printers,
    cura_definitions_dir,
    extract_slice_stats,
    parse_bambox_headers,
)


class TestCuraDefinitions:
    def test_definitions_dir_exists(self) -> None:
        d = cura_definitions_dir()
        assert d.exists()
        assert d.is_dir()

    def test_available_printers(self) -> None:
        printers = available_cura_printers()
        assert "bambox_p1s" in printers


class TestP1sNativeDefinition:
    """Tests for the native single-extruder P1S definition (no post-processing)."""

    def test_p1s_definition_valid_json(self) -> None:
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        assert data["version"] == 2
        assert data["inherits"] == "fdmprinter"

    def test_p1s_single_extruder(self) -> None:
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        assert data["overrides"]["machine_extruder_count"]["value"] == 1

    def test_p1s_has_single_extruder_train(self) -> None:
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        trains = data["metadata"]["machine_extruder_trains"]
        assert len(trains) == 1
        assert "0" in trains
        assert trains["0"] == "bambox_p1s_extruder_0"

    def test_p1s_extruder_definition_exists(self) -> None:
        ext = cura_definitions_dir() / "bambox_p1s_extruder_0.def.json"
        assert ext.exists()

    def test_p1s_extruder_valid_json(self) -> None:
        ext = cura_definitions_dir() / "bambox_p1s_extruder_0.def.json"
        data = json.loads(ext.read_text())
        assert data["version"] == 2
        assert data["metadata"]["machine"] == "bambox_p1s"
        assert data["metadata"]["position"] == "0"

    def test_p1s_start_gcode_has_full_sequence(self) -> None:
        """Start gcode must contain the complete P1S startup sequence."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        start = data["overrides"]["machine_start_gcode"]["default_value"]
        # Heatbed preheat
        assert "M140 S{material_bed_temperature_layer_0}" in start
        assert "M190 S{material_bed_temperature_layer_0}" in start
        # Nozzle temp
        assert "M104 S{material_print_temperature_layer_0}" in start
        assert "M109 S{material_print_temperature_layer_0}" in start
        # PLA fan conditional
        assert '{if material_type == "PLA"}' in start
        # Bed leveling
        assert "G29 A" in start
        # Nozzle wipe sequence
        assert "wipe nozzle" in start
        # Nozzle load line
        assert "nozzle load line" in start
        # Textured PEI plate conditional
        assert '{if machine_buildplate_type == "textured_pei_plate"}' in start
        assert "G29.1 Z-0.04" in start

    def test_p1s_start_gcode_no_bambox_assemble(self) -> None:
        """Native definition must NOT have BAMBOX_ASSEMBLE — gcode is complete."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        start = data["overrides"]["machine_start_gcode"]["default_value"]
        assert "BAMBOX_ASSEMBLE" not in start

    def test_p1s_end_gcode_no_max_layer_z(self) -> None:
        """End gcode must not reference max_layer_z (unavailable in CuraEngine)."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        end = data["overrides"]["machine_end_gcode"]["default_value"]
        assert "max_layer_z" not in end

    def test_p1s_end_gcode_uses_relative_z_lift(self) -> None:
        """End gcode uses G91 relative move instead of max_layer_z for Z lift."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        end = data["overrides"]["machine_end_gcode"]["default_value"]
        assert "G91" in end
        assert "G1 Z0.5 F900" in end
        assert "G90" in end

    def test_p1s_end_gcode_uses_machine_height_for_z_drop(self) -> None:
        """End gcode uses {machine_height} variable for bed drop."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        end = data["overrides"]["machine_end_gcode"]["default_value"]
        assert "{machine_height}" in end

    def test_p1s_end_gcode_has_full_sequence(self) -> None:
        """End gcode must contain the complete P1S shutdown sequence."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        end = data["overrides"]["machine_end_gcode"]["default_value"]
        assert "M140 S0" in end  # bed off
        assert "M104 S0" in end  # hotend off
        assert "M106 S0" in end  # fan off
        assert "M73 P100 R0" in end  # 100% complete signal
        assert "G92 E0" in end  # zero extruder

    def test_p1s_no_jinja2_syntax(self) -> None:
        """Native definition must not contain Jinja2 syntax."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        text = defn.read_text()
        assert "{{" not in text
        assert "}}" not in text
        assert "{%" not in text
        assert "%}" not in text

    def test_p1s_has_roofing_flooring_counts(self) -> None:
        """CuraEngine 5.12+ requires explicit roofing/flooring_layer_count."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        overrides = data["overrides"]
        assert "roofing_layer_count" in overrides
        assert "flooring_layer_count" in overrides

    def test_p1s_end_gcode_has_ams_unload(self) -> None:
        """End gcode must retract filament back to AMS."""
        defn = cura_definitions_dir() / "bambox_p1s.def.json"
        data = json.loads(defn.read_text())
        end = data["overrides"]["machine_end_gcode"]["default_value"]
        assert "M620 S255" in end
        assert "T255" in end
        assert "M621 S255" in end


class TestParseBamboxHeaders:
    def test_basic_headers(self) -> None:
        gcode = (
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_BED_TEMP=60\n"
            "; BAMBOX_ASSEMBLE=true\n"
            "; BAMBOX_END\n"
            "G28\n"
        )
        h = parse_bambox_headers(gcode)
        assert h["PRINTER"] == "p1s"
        assert h["BED_TEMP"] == "60"
        assert h["ASSEMBLE"] == "true"

    def test_stops_at_bambox_end(self) -> None:
        gcode = "; BAMBOX_PRINTER=p1s\n; BAMBOX_END\n; BAMBOX_IGNORED=yes\n"
        h = parse_bambox_headers(gcode)
        assert "IGNORED" not in h

    def test_multi_value_keys(self) -> None:
        """Multiple BAMBOX_FILAMENT_TYPE lines become comma-separated."""
        gcode = "; BAMBOX_FILAMENT_TYPE=PLA\n; BAMBOX_FILAMENT_TYPE=PETG-CF\n; BAMBOX_END\n"
        h = parse_bambox_headers(gcode)
        assert h["FILAMENT_TYPE"] == "PLA,PETG-CF"

    def test_multi_slot_headers(self) -> None:
        """Simulates CuraEngine output with per-extruder headers."""
        gcode = (
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_EXTRUDERS=4\n"
            "; BAMBOX_ASSEMBLE=true\n"
            "G28\n"
            ";TYPE:CUSTOM\n"
            "; BAMBOX_FILAMENT_SLOT=0\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
            "T0\n"
            "G1 X10 Y10 E1 F600\n"
        )
        h = parse_bambox_headers(gcode)
        assert h["PRINTER"] == "p1s"
        assert h["EXTRUDERS"] == "4"
        assert h["FILAMENT_SLOT"] == "0"
        assert h["FILAMENT_TYPE"] == "PLA"

    def test_no_bambox_headers(self) -> None:
        gcode = "G28\nG1 Z0.2 F1200\n"
        h = parse_bambox_headers(gcode)
        assert h == {}

    def test_mixed_with_regular_comments(self) -> None:
        gcode = (
            "; generated by CuraEngine\n"
            ";FLAVOR:Marlin\n"
            "; BAMBOX_PRINTER=p1s\n"
            ";TIME:1234\n"
            "; BAMBOX_END\n"
        )
        h = parse_bambox_headers(gcode)
        assert h["PRINTER"] == "p1s"
        # Defaults are injected for missing machine-level headers
        assert h["NOZZLE_DIAMETER"] == "0.4"
        assert h["BED_TYPE"] == "Textured PEI Plate"

    def test_full_scan_finds_filament_headers_after_bambox_end(self) -> None:
        """Per-extruder headers (FILAMENT_SLOT/TYPE) appear at tool-change
        points throughout the file, well past the machine_start_gcode block.
        parse_bambox_headers must scan the entire file for these keys."""
        gcode = (
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_BED_TEMP=60\n"
            "; BAMBOX_ASSEMBLE=true\n"
            "; BAMBOX_FILAMENT_SLOT=0\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
            "; BAMBOX_END\n" + "G1 X0 Y0\n" * 500 + "; BAMBOX_FILAMENT_SLOT=3\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
        )
        h = parse_bambox_headers(gcode)
        assert h["PRINTER"] == "p1s"
        assert h["FILAMENT_SLOT"] == "0,3"
        assert h["FILAMENT_TYPE"] == "PLA,PLA"


class TestPackWithBamboxHeaders:
    def test_auto_configures_from_headers(self, tmp_path: Path) -> None:
        """pack should auto-detect machine/filament from BAMBOX headers."""
        gcode_file = tmp_path / "cura_output.gcode"
        gcode_file.write_text(
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_FILAMENT_TYPE=PETG-CF\n"
            "; BAMBOX_BED_TEMP=80\n"
            "; BAMBOX_NOZZLE_TEMP=260\n"
            "; BAMBOX_END\n"
            "G28\nG1 Z0.2 F1200\nG1 X10 Y10 E1 F600\n"
        )
        output = tmp_path / "output.gcode.3mf"

        # No -f flag — headers should provide filament
        main(["pack", str(gcode_file), "-o", str(output)])

        with zipfile.ZipFile(output) as z:
            ps = json.loads(z.read("Metadata/project_settings.config"))
            # Should have detected PETG-CF from headers
            assert ps["filament_type"][0] == "PETG-CF"
            assert len(ps) > 500

    def test_headers_override_cli_filament(self, tmp_path: Path) -> None:
        """BAMBOX_FILAMENT_TYPE header takes precedence over --filament flag."""
        gcode_file = tmp_path / "cura_output.gcode"
        gcode_file.write_text(
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
            "; BAMBOX_END\n"
            "G28\nG1 Z0.2 F1200\nG1 X10 Y10 E1 F600\n"
        )
        output = tmp_path / "override.gcode.3mf"

        main(["pack", str(gcode_file), "-o", str(output), "-f", "PETG-CF"])

        with zipfile.ZipFile(output) as z:
            ps = json.loads(z.read("Metadata/project_settings.config"))
            # Header should win over CLI flag
            assert ps["filament_type"][0] == "PLA"

    def test_multi_filament_from_headers(self, tmp_path: Path) -> None:
        """Multiple BAMBOX_FILAMENT_TYPE headers become multi-filament."""
        gcode_file = tmp_path / "multi.gcode"
        gcode_file.write_text(
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
            "; BAMBOX_FILAMENT_TYPE=PETG-CF\n"
            "; BAMBOX_END\n"
            "G28\nG1 Z0.2 F1200\nG1 X10 Y10 E1 F600\n"
        )
        output = tmp_path / "multi.gcode.3mf"

        main(["pack", str(gcode_file), "-o", str(output)])

        with zipfile.ZipFile(output) as z:
            ps = json.loads(z.read("Metadata/project_settings.config"))
            assert ps["filament_type"][0] == "PLA"
            assert ps["filament_type"][1] == "PETG-CF"

    def test_slot_mapping_from_cli(self, tmp_path: Path) -> None:
        """bambox pack -f 3:PETG-CF places filament in slot 3."""
        gcode_file = tmp_path / "slot.gcode"
        gcode_file.write_text("G28\nG1 Z0.2 F1200\nG1 X10 Y10 E1 F600\n")
        output = tmp_path / "slot.gcode.3mf"

        main(["pack", str(gcode_file), "-o", str(output), "-f", "3:PETG-CF"])

        with zipfile.ZipFile(output) as z:
            ps = json.loads(z.read("Metadata/project_settings.config"))
            assert ps["filament_type"][0] == "PETG-CF"

    def test_slot_mapping_from_headers(self, tmp_path: Path) -> None:
        """BAMBOX_FILAMENT_SLOT headers auto-configure slot assignment.

        CuraEngine emits paired SLOT+TYPE in machine_extruder_start_code."""
        gcode_file = tmp_path / "slot_header.gcode"
        gcode_file.write_text(
            "; BAMBOX_PRINTER=p1s\n"
            "; BAMBOX_FILAMENT_SLOT=0\n"
            "; BAMBOX_FILAMENT_TYPE=PLA\n"
            "G28\nG1 Z0.2 F1200\n"
            "; BAMBOX_FILAMENT_SLOT=2\n"
            "; BAMBOX_FILAMENT_TYPE=PETG-CF\n"
            "; BAMBOX_END\n"
            "G1 X10 Y10 E1 F600\n"
        )
        output = tmp_path / "slot_header.gcode.3mf"

        main(["pack", str(gcode_file), "-o", str(output)])

        with zipfile.ZipFile(output) as z:
            ps = json.loads(z.read("Metadata/project_settings.config"))
            assert ps["filament_type"][0] == "PLA"
            assert ps["filament_type"][1] == "PETG-CF"


class TestParseFilamentArgs:
    def test_type_only(self) -> None:
        result = _parse_filament_args(["PLA"])
        assert result == [(None, "PLA", "#F2754E")]

    def test_type_color(self) -> None:
        result = _parse_filament_args(["PLA:#FF0000"])
        assert result == [(None, "PLA", "#FF0000")]

    def test_slot_type(self) -> None:
        result = _parse_filament_args(["3:PETG-CF"])
        assert result == [(3, "PETG-CF", "#F2754E")]

    def test_slot_type_color(self) -> None:
        result = _parse_filament_args(["2:PETG-CF:#2850E0"])
        assert result == [(2, "PETG-CF", "#2850E0")]

    def test_default(self) -> None:
        result = _parse_filament_args(None)
        assert result == [(None, "PLA", "#F2754E")]


class TestAssignFilamentSlots:
    def test_sequential(self) -> None:
        parsed = [(None, "PLA", "#F2754E"), (None, "PETG-CF", "#F2754E")]
        result = _assign_filament_slots(parsed)
        assert result == [(0, "PLA", "#F2754E"), (1, "PETG-CF", "#F2754E")]

    def test_explicit_slot(self) -> None:
        parsed = [(3, "PETG-CF", "#F2754E")]
        result = _assign_filament_slots(parsed)
        assert result == [(3, "PETG-CF", "#F2754E")]

    def test_mixed_explicit_and_sequential(self) -> None:
        parsed = [(None, "PLA", "#F2754E"), (2, "PETG-CF", "#2850E0")]
        result = _assign_filament_slots(parsed)
        assert result == [(0, "PLA", "#F2754E"), (2, "PETG-CF", "#2850E0")]

    def test_explicit_slot_skips_for_sequential(self) -> None:
        """Unslotted filaments skip over explicitly claimed slots."""
        parsed = [(0, "PETG-CF", "#F2754E"), (None, "PLA", "#F2754E")]
        result = _assign_filament_slots(parsed)
        assert result == [(0, "PETG-CF", "#F2754E"), (1, "PLA", "#F2754E")]


class TestExtractSliceStats:
    def test_time_from_time_header_only(self) -> None:
        gcode = ";TIME:1234\nG1 X0\n"
        stats = extract_slice_stats(gcode)
        assert stats.prediction == 1234

    def test_time_from_time_elapsed_only(self) -> None:
        gcode = ";LAYER:0\nG1 X0\n;TIME_ELAPSED:500.0\n"
        stats = extract_slice_stats(gcode)
        assert stats.prediction == 500

    def test_time_prefers_elapsed_over_time_header(self) -> None:
        """;TIME: is often a CuraEngine default (6666); prefer TIME_ELAPSED."""
        gcode = ";TIME:6666\n;LAYER:0\nG1 X0\n;TIME_ELAPSED:2799.0\n"
        stats = extract_slice_stats(gcode)
        assert stats.prediction == 2799

    def test_time_falls_back_to_time_header(self) -> None:
        """When no TIME_ELAPSED is present, fall back to ;TIME:."""
        gcode = ";TIME:1500\nG1 X0\n"
        stats = extract_slice_stats(gcode)
        assert stats.prediction == 1500

    def test_no_time_info(self) -> None:
        gcode = "G28\nG1 X0\n"
        stats = extract_slice_stats(gcode)
        assert stats.prediction == 0

    def test_filament_used_parsing(self) -> None:
        gcode = ";Filament used: 1.234m, 0.567m\n"
        stats = extract_slice_stats(gcode)
        assert stats.filament_used_m == [1.234, 0.567]
        assert stats.weight > 0

    def test_weight_from_e_positions(self) -> None:
        """When Filament used is 0m, compute weight from E positions."""
        gcode = ";Filament used: 0m\nG92 E0\nG1 X10 E5.0\nG1 X20 E10.0\n"
        stats = extract_slice_stats(gcode)
        assert stats.weight > 0
