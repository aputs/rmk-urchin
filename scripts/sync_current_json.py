#!/usr/bin/env python3
"""Regenerate current.json (Vial keymap state export) from keyboard.toml.

current.json is the state you import into the Vial web UI to view/edit the
keymap. The firmware itself is compiled from keyboard.toml, so this keeps
current.json consistent with what is actually flashed.

Translation / position rules (reverse-engineered from the existing file):
  - MT(base,Mod)      -> MOD_T(KC_base)
  - LT(n,key)         -> LTn(KC_key)
  - WM(base,Mod)      -> MOD(KC_base)          (parens, not _T)
  - SHIFTED(key)      -> LSFT(KC_key)
  - No                -> KC_NO
  - _ (transparent)   -> KC_TRNS, EXCEPT the 6 unwired thumb-row placeholders
                         (row 3, cols 0,1,2,7,8,9) -> -1
  - a handful of RMK action names -> their Vial KC_ aliases (see SPECIAL).
"""
import json
import re
import sys

ROOT = "/Volumes/projects/rmk-urchin"

MOD_MAP = {
    "LGUI": "LGUI", "LALT": "LALT", "LCTRL": "LCTRL", "LSFT": "LSFT",
    "RSFT": "RSFT", "RCTRL": "RCTRL", "RALT": "RALT",
}
# normalise friendly names (upper-cased) to the short Vial export form
MOD_ALIASES = {
    "LGUI": "LGUI", "LALT": "LALT", "RALT": "RALT",
    "LCTRL": "L" + "CTL",  # L,C,T,L  -> matches original 'LCTRL'
    "RCTRL": "R" + "CTL",  # R,C,T,L  -> matches original 'RCTRL'
    "LSHIFT": "LSFT", "RSHIFT": "RSFT",
}

# aliases for the base keycode of MT/LT/WM/SHIFTED (Vial short forms)
BASE_ALIASES = {
    "BACKSPACE": "KC_BSPACE", "BSLS": "KC_BSLASH", "SEMICOLON": "KC_SCOLON",
}

SPECIAL = {
    "BACKSPACE": "KC_BSPACE", "BSLS": "KC_BSLASH", "SEMICOLON": "KC_SCOLON",
    "LEFTBRACKET": "KC_LBRACKET", "RIGHTBRACKET": "KC_RBRACKET",
    "PAGEUP": "KC_PGUP", "PAGEDOWN": "KC_PGDOWN", "DELETE": "KC_DELETE",
    "AUDIOVOLDOWN": "KC_VOLD", "AUDIOVOLUP": "KC_VOLU",
    "MEDIAPLAYPAUSE": "KC_MPLY", "MEDIASTOP": "KC_MSTP",
    "QK_BOOT": "QK_BOOT", "BOOTLOADER": "QK_BOOT", "REBOOT": "QK_REBOOT",
    "CLEAREEPROM": "QK_CLEAR_EEPROM",
}

UNWIRED_THUMB = {0, 1, 2, 7, 8, 9}


def split_top(inner, sep=","):
    """Split on the first top-level comma (values have no nested parens here)."""
    idx = inner.find(sep)
    return inner[:idx].strip(), inner[idx + len(sep):].strip()


def conv(tok, row, col):
    tok = tok.strip()
    if tok == "" or tok == "_":
        if row == 3 and col in UNWIRED_THUMB:
            return -1
        return "KC_TRNS"
    up = tok.upper()

    def base_tok(name):
        return BASE_ALIASES.get(name.upper(), "KC_" + name.upper())

    if up.startswith("MT("):
        inner = tok[3:-1]
        base, mod = split_top(inner)
        mod = mod.split(",")[0].strip()  # drop the morse profile name; Vial has no slot for it
        m = MOD_ALIASES.get(mod.upper(), mod.upper())
        return f"{m}_T({base_tok(base)})"
    if up.startswith("LT("):
        inner = tok[3:-1]
        n, key = split_top(inner)
        key = key.split(",")[0].strip()  # drop the morse profile name
        return f"LT{n}({base_tok(key)})"
    if up.startswith("WM("):
        inner = tok[3:-1]
        base, mod = split_top(inner)
        m = MOD_ALIASES.get(mod.upper(), mod.upper())
        return f"{m}({base_tok(base)})"
    if up.startswith("SHIFTED("):
        key = tok[8:-1]
        return f"LSFT({base_tok(key)})"
    if up.startswith("USER"):
        return up  # USER06 -> USER06
    return SPECIAL.get(up, "KC_" + up)


def parse_layers(path):
    text = open(path).read()
    # grab each [[keymap.layer]] block's keys = """ ... """
    layers = []
    for m in re.finditer(r'\[\[keymap\.layer\]\](.*?)(?=\[\[keymap\.layer\]|\Z)',
                         text, re.S):
        block = m.group(1)
        km = re.search(r'keys\s*=\s*"""(.*?)"""', block, re.S)
        if not km:
            continue
        rows = [r for r in km.group(1).strip().splitlines() if r.strip()]
        layers.append(rows)
    return layers


def build_layout(rows):
    layout = []
    for r, row in enumerate(rows):
        toks = row.split()
        cell = []
        for c, tok in enumerate(toks):
            cell.append(conv(tok, r, c))
        # pad/truncate to 10 cols to stay well-formed
        while len(cell) < 10:
            cell.append(-1 if (r == 3 and len(cell) in UNWIRED_THUMB) else "KC_TRNS")
        layout.append(cell[:10])
    return layout


def main():
    layers = parse_layers(f"{ROOT}/keyboard.toml")
    if len(layers) != 5:
        print(f"warning: expected 5 layers, found {len(layers)}", file=sys.stderr)
    new_layout = [build_layout(l) for l in layers]

    src = json.load(open(f"{ROOT}/current.json"))
    out = {"version": src.get("version", 1),
           "uid": src.get("uid"),
           "layout": new_layout}
    json.dump(out, open(f"{ROOT}/current.json", "w"), separators=(",", ":"))
    print(f"wrote current.json ({len(layers)} layers)")


if __name__ == "__main__":
    main()
