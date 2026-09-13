#!/usr/bin/env python3
"""Reverse of sync_current_json.py: rewrite keyboard.toml's [[keymap.layer]]
blocks from current.json (Vial keymap state). [behavior.morse] timeouts and all
other sections sit AFTER the keymap blocks, so they are kept verbatim -> the
keyboard.toml timeouts win.

Vial -> RMK keymap notation (spelling chosen so the result recompiles):
  LGUI_T(KC_S)          -> MT(S,LGui)
  LT2(KC_ENTER)         -> LT(2,ENTER)
  RCTL(KC_BSLASH)       -> WM(BSLS,RCtrl)
  LSFT(KC_MINUS)        -> SHIFTED(Minus)
  QK_BOOT / QK_REBOOT / QK_CLEAR_EEPROM -> Bootloader / Reboot / ClearEeprom
  USER04                -> User04
  KC_<NAME>             -> title-cased name or a short alias (BSLS, Comma, ...)
  KC_TRNS or -1         -> _
"""
import json
import re
import sys

ROOT = "/Volumes/projects/rmk-urchin"

# keys must match the Vial token spelling exactly: LCTL/RCTL = L,C,T,L / R,C,T,L (no R)
MOD = {"LGUI": "LGui", "LALT": "LAlt", "LCTL": "LCtrl", "LSFT": "LShift",
       "RSFT": "RShift", "RCTL": "RCtrl", "RALT": "RAlt", "RGUI": "RGui"}

# standalone KC_<NAME> aliases (keys are the full Vial/QMK keycode name)
SPECIAL_KC = {"BSLASH": "BSLS", "COMMA": "Comma", "DOT": "Dot", "SLASH": "Slash",
              "NO": "No", "DELETE": "Delete", "PGUP": "PageUp", "PGDOWN": "PageDown",
              "VOLD": "AudioVolDown", "VOLU": "AudioVolUp",
              "MPLY": "MediaPlayPause", "MSTP": "MediaStop",
              # standalone modifiers (title-case would give Lgui/Lctrl -> keep RMK form)
              # note: Vial stores these as KC_LGUI/KC_LSHIFT (full names), unlike the
              # compact LSFT/RCTL used as mod-tap prefixes
              "LGUI": "LGui", "LALT": "LAlt", "LCTRL": "LCtrl", "LSHIFT": "LShift",
              "RSHIFT": "RShift", "RCTRL": "RCtrl", "RALT": "RAlt", "RGUI": "RGui",
              # bracket / semicolon full words
              "LBRACKET": "LeftBracket", "RBRACKET": "RightBracket", "SCOLON": "Semicolon"}

# base keycode inside MT/LT/WM/SHIFTED (keys are the full Vial/QMK keycode name)
BASE_KC = {"BSPACE": "Backspace", "BSLASH": "BSLS", "SCOLON": "Semicolon",
           "MINUS": "Minus", "EQUAL": "Equal", "QUOTE": "Quote", "GRAVE": "Grave",
           # these stay upper-case in keyboard.toml
           "ENTER": "ENTER", "TAB": "TAB", "SPACE": "SPACE"}

QK = {"QK_BOOT": "Bootloader", "QK_REBOOT": "Reboot", "QK_CLEAR_EEPROM": "ClearEeprom"}


def kc_name(x):
    if len(x) == 1:
        return x.upper()   # Q, D, A, Z ... match original keyboard.toml
    if x in SPECIAL_KC:
        return SPECIAL_KC[x]
    return x.title()  # GRAVE->Grave, SCOLON->Semicolon, LBRACKET->LeftBracket, F12->F12


def base_name(x):
    if len(x) == 1:
        return x.upper()   # MT(S,...) base S, LT(1,TAB) base ...
    if x in BASE_KC:
        return BASE_KC[x]
    return x.title()  # TAB->Tab, ENTER->Enter, SPACE->Space


# Vial JSON carries no morse profile, so re-attach the ones defined in
# [behavior.morse.profiles]: home-row mod-taps -> HRM, thumb layer-taps -> THUMB.
MT_PROFILE = "HRM"
LT_PROFILE = "THUMB"


def rev(tok):
    if isinstance(tok, int):
        return "_"
    tok = tok.strip()
    if tok == "-1" or tok == "KC_TRNS":
        return "_"
    m = re.match(r"^([A-Za-z]+)_T\(KC_(.+)\)$", tok)   # mod-tap
    if m:
        return f"MT({base_name(m.group(2))},{MOD[m.group(1)]},{MT_PROFILE})"
    m = re.match(r"^LSFT\(KC_(.+)\)$", tok)            # shift-tap / shifted
    if m:
        return f"SHIFTED({base_name(m.group(1))})"
    m = re.match(r"^([A-Za-z]+)\(KC_(.+)\)$", tok)     # wrap mod-tap
    if m:
        return f"WM({base_name(m.group(2))},{MOD[m.group(1)]})"
    m = re.match(r"^LT(\d+)\(KC_(.+)\)$", tok)         # layer-tap
    if m:
        return f"LT({m.group(1)},{base_name(m.group(2))},{LT_PROFILE})"
    if tok.startswith("USER"):
        return "User" + tok[4:]
    if tok.startswith("QK_"):
        return QK.get(tok, tok)
    if tok.startswith("KC_"):
        return kc_name(tok[3:])
    return tok


def render_layer(layer):
    cells = [c for row in layer for c in row]   # flatten 2D layout
    rows = [cells[i:i + 10] for i in range(0, len(cells), 10)]
    return "\n".join(" ".join(rev(c) for c in r) for r in rows)


def main():
    d = json.load(open(f"{ROOT}/current.json"))
    new_blocks = "\n".join(
        f"[[keymap.layer]] # layer {i}\nkeys = \"\"\"\n{render_layer(layer)}\n\"\"\"\n"
        for i, layer in enumerate(d["layout"])
    )
    new_blocks += "\n"

    lines = open(f"{ROOT}/keyboard.toml").read().splitlines(keepends=True)

    first = next(i for i, l in enumerate(lines) if l.lstrip().startswith("[[keymap.layer]]"))
    last = max(i for i, l in enumerate(lines) if l.lstrip().startswith("[[keymap.layer]]"))
    # tail begins at the first real section header after the last keymap block
    tail = next(i for i in range(last + 1, len(lines)) if lines[i].lstrip().startswith("["))

    head = "".join(lines[:first])
    kept = "".join(lines[tail:])

    out = head + new_blocks + kept
    open(f"{ROOT}/keyboard.toml", "w").write(out)
    print(f"rewrote {len(d['layout'])} keymap layers (lines {first + 1}..{tail}); kept tail from line {tail + 1}")


if __name__ == "__main__":
    main()
