"""Declare sampled depth resources in SPIR-V before translation to WGSL.

Vulkan permits sampling a depth view through GLSL sampler2D. WebGPU requires a
texture_depth type in the shader. The binding contract supplies this information
which GLSL's type system cannot express without enabling comparison sampling.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Instruction:
    line: str
    result: str | None
    op: str
    args: list[str]

    def replace(self, args: list[str]) -> None:
        self.args = args
        prefix = f"{self.result} = " if self.result else ""
        self.line = prefix + self.op + " " + " ".join(args)


def declare_depth(assembly: str, bindings: list[tuple[int, int]]) -> str:
    """Retype named direct global image loads, refusing unsupported uses."""
    instructions = []
    for line in assembly.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith(";"):
            instructions.append(Instruction(line, None, "", []))
        elif len(parts) > 2 and parts[1] == "=":
            instructions.append(Instruction(line, parts[0], parts[2], parts[3:]))
        else:
            instructions.append(Instruction(line, None, parts[0], parts[1:]))
    definitions = {inst.result: inst for inst in instructions if inst.result}
    decorations: dict[str, dict[str, str]] = {}
    for inst in instructions:
        if inst.op == "OpDecorate" and inst.args[1] in ("DescriptorSet", "Binding"):
            decorations.setdefault(inst.args[0], {})[inst.args[1]] = inst.args[2]
    additions: dict[str, list[str]] = {}
    for index, (group, binding) in enumerate(bindings):
        matches = [
            name
            for name, values in decorations.items()
            if values.get("DescriptorSet") == str(group)
            and values.get("Binding") == str(binding)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"depth binding {group}:{binding}: matched {len(matches)} resources"
            )
        variable = definitions[matches[0]]
        pointer = definitions[variable.args[0]]
        image = definitions[pointer.args[1]]
        if (
            variable.op != "OpVariable"
            or pointer.op != "OpTypePointer"
            or image.op != "OpTypeImage"
        ):
            raise ValueError(f"depth binding {group}:{binding} is not a global image")
        if image.args[1] not in ("2D", "Cube") or image.args[5] != "1":
            raise ValueError(
                f"depth binding {group}:{binding} is not a sampleable depth image"
            )
        image_id = f"%web_depth_image_{index}"
        pointer_id = f"%web_depth_pointer_{index}"
        sampled_id = f"%web_depth_sampled_{index}"
        if any(name in definitions for name in (image_id, pointer_id, sampled_id)):
            raise ValueError("input already contains generated depth type identifiers")
        image_args = list(image.args)
        image_args[2] = "1"  # OpTypeImage Depth operand, per SPIR-V grammar.
        additions[variable.result] = [
            f"{image_id} = OpTypeImage {' '.join(image_args)}",
            f"{pointer_id} = OpTypePointer UniformConstant {image_id}",
            f"{sampled_id} = OpTypeSampledImage {image_id}",
        ]
        variable.replace([pointer_id, *variable.args[1:]])
        loads = set()
        for inst in instructions:
            if variable.result not in inst.args or inst is variable:
                continue
            if inst.op in ("OpName", "OpDecorate", "OpEntryPoint"):
                continue
            if inst.op != "OpLoad" or inst.args[1] != variable.result:
                raise ValueError(
                    f"depth binding {group}:{binding}: unsupported {inst.op} image use"
                )
            inst.replace([image_id, *inst.args[1:]])
            loads.add(inst.result)
        if not loads:
            raise ValueError(f"depth binding {group}:{binding} has no image loads")
        for inst in instructions:
            if not loads.intersection(inst.args):
                continue
            if inst.op == "OpSampledImage" and inst.args[1] in loads:
                inst.replace([sampled_id, *inst.args[1:]])
            elif inst.op not in (
                "OpImageQuerySize",
                "OpImageQuerySizeLod",
                "OpImageQueryLevels",
                "OpImageQuerySamples",
                "OpImageFetch",
            ):
                raise ValueError(
                    f"depth binding {group}:{binding}: unsupported {inst.op} loaded-image use"
                )
    result = []
    for inst in instructions:
        result.extend(additions.get(inst.result, []))
        result.append(inst.line)
    return "\n".join(result) + "\n"
