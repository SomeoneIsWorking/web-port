"""Exercise actual SPIR-V splitting, translation and failure publication."""

from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import shaders


FRAGMENT = """#version 450
layout(set=2,binding=0) uniform sampler2D first_texture;
layout(set=2,binding=1) uniform sampler2D second_texture;
layout(location=0) out vec4 color;
void main() { color = texture(first_texture, vec2(0.25)) +
                      texture(second_texture, vec2(0.75)); }
"""


def test_combined_sampler_binding_slots(tmp_path):
    source = tmp_path / "sample.frag"
    source.write_text(FRAGMENT)
    output = tmp_path / "sample.wgsl"
    shaders.convert(source, output, stage="frag")
    text = output.read_text()
    for binding in range(4):
        assert f"@group(2) @binding({binding})" in text
    assert text.count(": texture_2d<f32>") == 2
    assert text.count(": sampler;") == 2
    assert "@fragment" in text


def test_include_is_a_nul_terminated_c_string(tmp_path):
    source = tmp_path / "sample.frag"
    source.write_text(FRAGMENT)
    output = tmp_path / "sample.inc"
    shaders.convert(source, output, stage="frag", include=True)
    test = tmp_path / "include.c"
    test.write_text(
        "#include <stdio.h>\nstatic const char shader[] =\n"
        '#include "sample.inc"\n;\n'
        "int main(void) { return fwrite(shader, 1, sizeof(shader)-1, "
        "stdout) == sizeof(shader)-1 ? 0 : 1; }\n"
    )
    executable = tmp_path / "include"
    subprocess.run(
        ["clang", "-Wall", "-Wextra", "-Werror", str(test), "-o", str(executable)],
        check=True,
    )
    compiled = subprocess.run([str(executable)], capture_output=True, check=True).stdout
    assert compiled == output.with_suffix(".inc.generated.wgsl").read_bytes()


def test_bad_spirv_preserves_last_valid_shader(tmp_path):
    source = tmp_path / "bad.spv"
    source.write_bytes(b"not SPIR-V")
    output = tmp_path / "existing.wgsl"
    output.write_text("previous valid shader")
    with pytest.raises(subprocess.CalledProcessError):
        shaders.convert(source, output)
    assert output.read_text() == "previous valid shader"


def test_source_cannot_be_overwritten(tmp_path):
    source = tmp_path / "source.spv"
    source.write_bytes(b"original")
    with pytest.raises(ValueError, match="different paths"):
        shaders.convert(source, source)
    assert source.read_bytes() == b"original"


def test_depth_sampler_preserves_other_images_and_raw_sampling(tmp_path):
    source = tmp_path / "depth.frag"
    source.write_text(
        FRAGMENT.replace("texture(", "textureLod(")
        .replace("vec2(0.25))", "vec2(0.25), 0.0)")
        .replace("vec2(0.75))", "vec2(0.75), 0.0)")
    )
    output = tmp_path / "depth.wgsl"
    shaders.convert(source, output, stage="frag", depth_samplers=((2, 1),))
    result = output.read_text()
    assert result.count(": texture_depth_2d;") == 1
    assert result.count(": texture_2d<f32>;") == 1
    assert "textureSampleCompare" not in result
    assert "textureSampleLevel" in result


def test_absent_depth_binding_refuses_without_publishing(tmp_path):
    source = tmp_path / "sample.frag"
    source.write_text(FRAGMENT)
    output = tmp_path / "sample.wgsl"
    output.write_text("previous")
    with pytest.raises(ValueError, match="matched 0 resources"):
        shaders.convert(source, output, stage="frag", depth_samplers=((2, 9),))
    assert output.read_text() == "previous"


def test_embedded_spirv_array_uses_same_conversion(tmp_path):
    source = tmp_path / "sample.frag"
    source.write_text(FRAGMENT)
    spirv = tmp_path / "sample.spv"
    subprocess.run(
        ["glslc", "-fshader-stage=frag", str(source), "-o", str(spirv)], check=True
    )
    header = tmp_path / "shaders.h"
    header.write_text(
        "static const unsigned char fixture[] = {"
        + ",".join(str(byte) for byte in spirv.read_bytes())
        + "};"
    )
    output = tmp_path / "sample.wgsl"
    shaders.convert(header, output, c_array="fixture")
    assert output.read_text().count(": texture_2d<f32>;") == 2
    with pytest.raises(ValueError, match="matched 0 declarations"):
        shaders.convert(header, output, c_array="absent")


def test_byte_array_rejects_nonliteral_and_out_of_range():
    from shader_arrays import extract

    for data in ("function()", "0x100", "0x00,,0x01"):
        with pytest.raises(ValueError):
            extract("unsigned char fixture[] = {" + data + "};", "fixture")
