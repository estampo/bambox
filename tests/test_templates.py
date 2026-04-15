"""Test OrcaSlicer → Jinja2 template conversion."""

from __future__ import annotations

from bambox.templates import orca_to_jinja2

# ---------------------------------------------------------------------------
# OrcaSlicer → Jinja2 conversion
# ---------------------------------------------------------------------------


class TestOrcaToJinja2:
    """Test the syntax converter."""

    def test_simple_variable_curly(self) -> None:
        assert orca_to_jinja2("{bed_temperature}") == "{{ bed_temperature }}"

    def test_simple_variable_square(self) -> None:
        assert orca_to_jinja2("[bed_temperature]") == "{{ bed_temperature }}"

    def test_indexed_variable_curly(self) -> None:
        result = orca_to_jinja2("{filament_type[initial_extruder]}")
        assert result == "{{ filament_type[initial_extruder] }}"

    def test_expression(self) -> None:
        result = orca_to_jinja2("{max_layer_z + 0.5}")
        assert result == "{{ max_layer_z + 0.5 }}"

    def test_complex_expression(self) -> None:
        result = orca_to_jinja2("{filament_max_volumetric_speed[initial_extruder]/2.4053*60}")
        assert result == "{{ filament_max_volumetric_speed[initial_extruder]/2.4053*60 }}"

    def test_if_block(self) -> None:
        template = '{if filament_type[0]=="PLA"}\nM106 P3 S180\n{endif}'
        expected = '{% if filament_type[0]=="PLA" %}\nM106 P3 S180\n{% endif %}'
        assert orca_to_jinja2(template) == expected

    def test_elsif_block(self) -> None:
        template = '{if x=="A"}\nA\n{elsif x=="B"}\nB\n{else}\nC\n{endif}'
        expected = '{% if x=="A" %}\nA\n{% elif x=="B" %}\nB\n{% else %}\nC\n{% endif %}'
        assert orca_to_jinja2(template) == expected

    def test_endif_with_trailing_comment(self) -> None:
        result = orca_to_jinja2("{endif};Prevent PLA from jamming")
        assert result == "{% endif %};Prevent PLA from jamming"

    def test_mixed_line(self) -> None:
        """Variable embedded in a G-code command."""
        result = orca_to_jinja2("G1 Z{max_layer_z + 0.5} F900")
        assert result == "G1 Z{{ max_layer_z + 0.5 }} F900"

    def test_plain_gcode_unchanged(self) -> None:
        line = "G28 ; home all axes"
        assert orca_to_jinja2(line) == line

    def test_m_command_with_square_bracket(self) -> None:
        result = orca_to_jinja2("M140 S[bed_temperature_initial_layer_single]")
        assert result == "M140 S{{ bed_temperature_initial_layer_single }}"

    def test_indented_if(self) -> None:
        result = orca_to_jinja2("    {if x > 5}")
        assert result == "    {% if x > 5 %}"

    def test_multiple_vars_one_line(self) -> None:
        result = orca_to_jinja2("G29 A X{min[0]} Y{min[1]}")
        assert result == "G29 A X{{ min[0] }} Y{{ min[1] }}"


class TestOrcaControlFlowInExpression:
    """Test that control flow keywords inside {expr} are not double-converted (line 74)."""

    def test_control_flow_keyword_in_expression_preserved(self) -> None:
        result = orca_to_jinja2("{if x > 5}")
        assert result == "{% if x > 5 %}"

    def test_square_bracket_inside_jinja2_expression(self) -> None:
        """Square bracket vars inside {{ }} should not be double-converted."""
        result = orca_to_jinja2("{filament_type[extruder]}")
        assert result == "{{ filament_type[extruder] }}"

    def test_logical_operators_converted(self) -> None:
        """|| and && in conditions should become 'or' and 'and'."""
        result = orca_to_jinja2("{if x > 5 || y < 3}")
        assert result == "{% if x > 5  or  y < 3 %}"

        result = orca_to_jinja2("{if x > 5 && y < 3}")
        assert result == "{% if x > 5  and  y < 3 %}"
