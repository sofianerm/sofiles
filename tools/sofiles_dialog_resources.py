"""Format-aware Sofiles translations for Win32 dialog/string resource payloads.

These functions only parse and return bytes. They never load target DLLs or
write PE files. Running this module verifies the observed source resources via
pefile and writes a JSON validation note under analysis/branding/full-locales.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct


DIALOG_TEXT = {
    "IPC Logging Settings": "Journalisation de Sofiles",
    "All": "Tout",
    "None": "Aucun",
}
STRING_TEXT = {"TabHelper": "SofilesHelper"}
DS_SETFONT = 0x40


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def take(self, count: int) -> bytes:
        if count < 0 or self.offset + count > len(self.data):
            raise ValueError("Truncated or invalid Win32 resource")
        value = self.data[self.offset:self.offset + count]
        self.offset += count
        return value

    def word(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def atom(self) -> bytes:
        start = self.offset
        first = self.word()
        if first == 0xFFFF:
            self.take(2)
        elif first:
            while self.word():
                pass
        return self.data[start:self.offset]

    def align4(self) -> bytes:
        return self.take((-self.offset) % 4)


@dataclass(frozen=True)
class _Control:
    padding: bytes
    header: bytes
    window_class: bytes
    title: bytes
    creation_data: bytes


@dataclass(frozen=True)
class _Dialog:
    extended: bool
    header: bytes
    menu: bytes
    window_class: bytes
    title: bytes
    font: bytes
    controls: tuple[_Control, ...]
    tail: bytes


def _parse_dialog(data: bytes) -> _Dialog:
    if len(data) < 18:
        raise ValueError("Dialog resource is too short")
    reader = _Reader(data)
    first, signature = struct.unpack_from("<HH", data)
    extended = signature == 0xFFFF
    if extended:
        if first != 1:
            raise ValueError("Unsupported extended dialog version")
        header = reader.take(26)
        style = struct.unpack_from("<I", header, 12)[0]
        control_count = struct.unpack_from("<H", header, 16)[0]
    else:
        header = reader.take(18)
        style = struct.unpack_from("<I", header, 0)[0]
        control_count = struct.unpack_from("<H", header, 8)[0]
    menu, window_class, title = reader.atom(), reader.atom(), reader.atom()
    # The font is structural data, never a translated label.
    font = b""
    if style & DS_SETFONT:
        start = reader.offset
        reader.take(6 if extended else 2)
        reader.atom()
        font = data[start:reader.offset]
    controls = []
    for _ in range(control_count):
        padding = reader.align4()
        control_header = reader.take(24 if extended else 18)
        control_class, control_title = reader.atom(), reader.atom()
        start = reader.offset
        extra_count = reader.word()
        if extended:
            # DLGITEMTEMPLATEEX counts bytes FOLLOWING extraCount.
            reader.take(extra_count)
        elif extra_count:
            # DLGITEMTEMPLATE includes its size WORD in the byte count.
            if extra_count < 2:
                raise ValueError("Invalid standard dialog creation-data length")
            reader.take(extra_count - 2)
        controls.append(_Control(padding, control_header, control_class,
                                 control_title, data[start:reader.offset]))
    tail = data[reader.offset:]
    if len(tail) > 3 or any(tail):
        raise ValueError("Unrecognized data after dialog controls")
    return _Dialog(extended, header, menu, window_class, title, font,
                   tuple(controls), tail)


def _translated_atom(atom: bytes, replacements: dict[str, str]) -> bytes:
    if atom[:2] == b"\xff\xff":
        return atom  # An icon/resource ordinal must never be treated as text.
    text = atom[:-2].decode("utf-16le")
    replacement = replacements.get(text)
    if replacement is None:
        return atom
    if "\0" in replacement:
        raise ValueError("A dialog label cannot contain an embedded NUL")
    return replacement.encode("utf-16le") + b"\0\0"


def _write_dialog(dialog: _Dialog, replacements: dict[str, str]) -> bytes:
    output = bytearray(dialog.header + dialog.menu + dialog.window_class)
    output.extend(_translated_atom(dialog.title, replacements))
    output.extend(dialog.font)
    for control in dialog.controls:
        padding_size = (-len(output)) % 4
        # Retain original padding for an identity round trip. Length changes
        # require a new DWORD alignment; padding bytes have no control meaning.
        output.extend(control.padding if len(control.padding) == padding_size
                      else b"\0" * padding_size)
        output.extend(control.header)
        output.extend(control.window_class)
        output.extend(_translated_atom(control.title, replacements))
        output.extend(control.creation_data)
    output.extend(dialog.tail)
    return bytes(output)


def _dialog_structure(dialog: _Dialog) -> tuple:
    """Everything semantic except the dialog/control captions."""
    return (dialog.extended, dialog.header, dialog.menu, dialog.window_class,
            dialog.font, tuple((c.header, c.window_class, c.creation_data)
                               for c in dialog.controls), dialog.tail)


def translate_dialog(data: bytes) -> bytes:
    """Translate only the three known labels, preserving dialog metadata."""
    dialog = _parse_dialog(data)
    if _write_dialog(dialog, {}) != data:
        raise ValueError("Dialog identity round trip failed")
    translated = _write_dialog(dialog, DIALOG_TEXT)
    reparsed = _parse_dialog(translated)
    if _dialog_structure(reparsed) != _dialog_structure(dialog):
        raise ValueError("Dialog structural data changed")
    if _write_dialog(reparsed, {}) != translated:
        raise ValueError("Translated dialog identity round trip failed")
    return translated


def _parse_string_block(data: bytes) -> tuple[tuple[bytes, ...], bytes]:
    reader = _Reader(data)
    items = []
    for _ in range(16):
        length = reader.word()
        raw = reader.take(2 * length)
        raw.decode("utf-16le")  # Reject malformed text before constructing output.
        items.append(raw)
    tail = data[reader.offset:]
    if len(tail) > 3 or any(tail):
        raise ValueError("Unrecognized data after the 16 string-block entries")
    return tuple(items), tail


def _write_string_block(items: tuple[bytes, ...], tail: bytes = b"") -> bytes:
    if len(items) != 16:
        raise ValueError("A Win32 string block must have 16 entries")
    output = bytearray()
    for raw in items:
        if len(raw) % 2 or len(raw) // 2 > 0xFFFF:
            raise ValueError("Invalid UTF-16 string-block entry size")
        output.extend(struct.pack("<H", len(raw) // 2))
        output.extend(raw)
    output.extend(tail)
    return bytes(output)


def translate_string_block(data: bytes) -> bytes:
    """Rename the exact TabHelper display string, with UTF-16 WORD lengths."""
    items, tail = _parse_string_block(data)
    if _write_string_block(items, tail) != data:
        raise ValueError("String-block identity round trip failed")
    updated = tuple(STRING_TEXT.get(raw.decode("utf-16le"),
                                   raw.decode("utf-16le")).encode("utf-16le")
                    for raw in items)
    result = _write_string_block(updated, tail)
    if _parse_string_block(result) != (updated, tail):
        raise ValueError("Translated string-block round trip failed")
    return result


def _validate_original_resources() -> dict:
    # pefile reads resource ranges; it does not LoadLibrary or run target code.
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools/python-libs"))
    import pefile

    def read_resource(name, type_id, resource_id, language):
        pe = pefile.PE(str(root / "analysis/extracted" / name))
        try:
            for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if typ.id != type_id:
                    continue
                for item in typ.directory.entries:
                    if item.id != resource_id:
                        continue
                    for lang in item.directory.entries:
                        if lang.id == language:
                            entry = lang.data.struct
                            return pe.get_data(entry.OffsetToData, entry.Size)
        finally:
            pe.close()
        raise ValueError(f"Missing observed resource: {name}/{type_id}/{resource_id}/{language}")

    results = []
    dialog = read_resource("clover.dll", 5, 3000, 1033)
    translated = translate_dialog(dialog)
    before, after = _parse_dialog(dialog), _parse_dialog(translated)
    results.append({"file": "clover.dll", "resource": [5, 3000, 1033],
                    "bytes_before": len(dialog), "bytes_after": len(translated),
                    "dialog_format": "DIALOGEX" if before.extended else "DIALOG",
                    "control_count": len(before.controls),
                    "identity_roundtrip": _write_dialog(before, {}) == dialog,
                    "structural_metadata_unchanged": _dialog_structure(before) == _dialog_structure(after),
                    "translated_labels": DIALOG_TEXT,
                    "sha256_before": hashlib.sha256(dialog).hexdigest(),
                    "sha256_after": hashlib.sha256(translated).hexdigest()})
    for name in ["TabHelper32.dll", "TabHelper64.dll"]:
        original = read_resource(name, 6, 7, 2052)
        translated = translate_string_block(original)
        before, tail = _parse_string_block(original)
        after, new_tail = _parse_string_block(translated)
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        assert changed == [4] and after[4].decode("utf-16le") == "SofilesHelper"
        assert all(a == b for i, (a, b) in enumerate(zip(before, after)) if i not in changed)
        assert tail == new_tail
        results.append({"file": name, "resource": [6, 7, 2052],
                        "bytes_before": len(original), "bytes_after": len(translated),
                        "identity_roundtrip": _write_string_block(before, tail) == original,
                        "entry_count": len(after), "changed_entry_indices": changed,
                        "all_other_entries_unchanged": True,
                        "sha256_before": hashlib.sha256(original).hexdigest(),
                        "sha256_after": hashlib.sha256(translated).hexdigest()})
    # Exercise the standard layout separately. The actual target uses DIALOGEX.
    synthetic = (struct.pack("<IIHhhhh", 0x80000000, 0, 1, 0, 0, 80, 40)
                 + b"\0\0\0\0" + "IPC Logging Settings\0".encode("utf-16le"))
    synthetic += b"\0" * ((-len(synthetic)) % 4)
    synthetic += (struct.pack("<IIhhhhH", 0x50000000, 0, 1, 1, 30, 10, 42)
                  + struct.pack("<HH", 0xFFFF, 0x80)
                  + "All\0".encode("utf-16le") + b"\0\0")
    translated_synthetic = translate_dialog(synthetic)
    assert not _parse_dialog(translated_synthetic).extended
    return {"source_resources": results, "standard_dialog_synthetic_roundtrip": True,
            "target_execution": False, "pe_files_modified": False,
            "references": [
                "https://learn.microsoft.com/en-us/windows/win32/dlgbox/dlgtemplateex",
                "https://learn.microsoft.com/en-us/windows/win32/dlgbox/dlgitemtemplateex",
                "https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-dlgitemtemplate"]}


if __name__ == "__main__":
    report = _validate_original_resources()
    report_path = (Path(__file__).resolve().parents[1]
                   / "analysis/branding/full-locales/dialog-resource-validation.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
