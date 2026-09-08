"""Read byte-array shader artifacts emitted by SDL_shadercross."""

import re


def extract(source: str, name: str) -> bytes:
    declaration = re.compile(
        r"\bunsigned\s+char\s+" + re.escape(name) + r"\s*\[\s*\]\s*=\s*\{([^}]+)\}\s*;"
    )
    matches = declaration.findall(source)
    if len(matches) != 1:
        raise ValueError(
            f"shader byte array {name}: matched {len(matches)} declarations"
        )
    tokens = matches[0].strip().rstrip(",").split(",")
    if not all(
        re.fullmatch(r"\s*(?:0[xX][0-9a-fA-F]+|[0-9]+)\s*", token) for token in tokens
    ):
        raise ValueError(f"shader byte array {name} contains nonliteral bytes")
    values = [
        int(token.strip(), 16 if token.strip().lower().startswith("0x") else 10)
        for token in tokens
    ]
    if not values or any(value > 255 for value in values):
        raise ValueError(f"shader byte array {name} contains invalid byte values")
    return bytes(values)
