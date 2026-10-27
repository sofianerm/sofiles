"""Create a reversible branding preview. Never execute or load Clover code.

Only localized display strings and RT_VERSION display fields are changed.
Internal filenames, IPC names, registry keys and original author credits stay
intact. No installer or shell registration is run or generated here.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/python-libs"))
import pefile

SOURCE = ROOT / "analysis/extracted"
DEST = ROOT / "builds/Sofiles-0.1-branding"
REPORT = ROOT / "analysis/branding"
EXPECTED = {
    "clover.exe": "0fed815095121de712ee06f5dabd0e5f33ce3cb98225091132bce81c85adefd7",
    "clover.dll": "34c3b337dac6e111d9503e18a161773994032570e6ab9276eb9fb8769f751eef",
    "TabHelper32.dll": "71d376e0fa6d05c8832ce0a787892dcecfafb921184fbc7b24933f0a08eeadfe",
    "TabHelper64.dll": "986a2c3ba20338cb87bb11fd01f3b3eba0c3870b4aa5f4c55d3fc095a1543a4c",
}
# Preserve original authorship, project acknowledgement and unused placeholders.
CREDIT_IDS = {10011, 10012, 10013, 10014, 10015, 10016, 10017}
DISPLAY_FIELDS = {"FileDescription", "ProductName", "ProductShortName"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align4(n: int) -> int:
    return (n + 3) & ~3


@dataclass
class VersionNode:
    key: str
    kind: int
    value: bytes
    children: list[VersionNode] = field(default_factory=list)


def read_version(data: bytes, start=0, limit=None):
    limit = len(data) if limit is None else limit
    length, value_length, kind = struct.unpack_from("<HHH", data, start)
    end = start + length
    if length < 8 or end > limit or kind not in (0, 1):
        raise ValueError("Invalid version resource bounds")
    cursor = start + 6
    while cursor + 2 <= end and data[cursor:cursor + 2] != b"\0\0":
        cursor += 2
    if cursor + 2 > end:
        raise ValueError("Unterminated version key")
    key = data[start + 6:cursor].decode("utf-16le")
    cursor = align4(cursor + 2)
    value_bytes = value_length * (2 if kind == 1 else 1)
    if cursor + value_bytes > end:
        raise ValueError("Invalid version value length")
    node = VersionNode(key, kind, data[cursor:cursor + value_bytes])
    cursor = align4(cursor + value_bytes)
    while cursor + 6 <= end:
        if not any(data[cursor:end]):
            break
        child, next_cursor = read_version(data, cursor, end)
        node.children.append(child)
        cursor = align4(next_cursor)
    return node, end


def write_version(node: VersionNode) -> bytes:
    data = bytearray(b"\0" * 6 + node.key.encode("utf-16le") + b"\0\0")
    data.extend(b"\0" * (align4(len(data)) - len(data)))
    data.extend(node.value)
    for child in node.children:
        data.extend(b"\0" * (align4(len(data)) - len(data)))
        data.extend(write_version(child))
    value_length = len(node.value) // (2 if node.kind == 1 else 1)
    struct.pack_into("<HHH", data, 0, len(data), value_length, node.kind)
    return bytes(data)


def change_version(node: VersionNode, changes: list):
    if node.key in DISPLAY_FIELDS and node.kind == 1:
        before = node.value.decode("utf-16le").rstrip("\0")
        after = before.replace("Clover", "Sofiles")
        if before != after:
            node.value = after.encode("utf-16le") + b"\0\0"
            changes.append({"field": node.key, "before": before, "after": after})
    for child in node.children:
        change_version(child, changes)


def resources(pe):
    result = {}
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        type_key = str(typ.name) if typ.name else typ.id
        for name in typ.directory.entries:
            name_key = str(name.name) if name.name else name.id
            for lang in name.directory.entries:
                value = lang.data.struct
                result[(type_key, name_key, lang.id)] = pe.get_data(value.OffsetToData, value.Size)
    return result


def edit_pe_version(path: Path):
    before = pefile.PE(data=path.read_bytes())
    original_resources = resources(before)
    changes, replacements = [], {}
    for key, data in original_resources.items():
        if key[0] != 16:
            continue
        tree, _ = read_version(data)
        change_version(tree, changes)
        replacements[key] = write_version(tree)
    if not changes or len(replacements) != 1:
        raise ValueError(f"Unexpected version resource: {path.name}")

    # This is Windows' file-resource editing API. It does not LoadLibrary the target.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                      wintypes.WORD, ctypes.c_void_p, wintypes.DWORD]
    kernel.UpdateResourceW.restype = wintypes.BOOL
    kernel.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    kernel.EndUpdateResourceW.restype = wintypes.BOOL
    handle = kernel.BeginUpdateResourceW(str(path), False)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        for (typ, name, lang), data in replacements.items():
            buffer = ctypes.create_string_buffer(data)
            if not kernel.UpdateResourceW(handle, typ, name, lang, buffer, len(data)):
                raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.EndUpdateResourceW(handle, True)
        raise
    if not kernel.EndUpdateResourceW(handle, False):
        raise ctypes.WinError(ctypes.get_last_error())

    after = pefile.PE(data=path.read_bytes())
    updated_resources = resources(after)
    assert original_resources.keys() == updated_resources.keys()
    for key, data in original_resources.items():
        assert updated_resources[key] == replacements.get(key, data), (path.name, key)
    assert len(before.sections) == len(after.sections)
    unchanged_sections = []
    for original, updated in zip(before.sections, after.sections):
        assert original.Name == updated.Name
        assert original.VirtualAddress == updated.VirtualAddress
        assert original.Characteristics == updated.Characteristics
        if original.Name.rstrip(b"\0") != b".rsrc":
            assert original.get_data() == updated.get_data(), (path.name, original.Name)
            unchanged_sections.append(original.Name.rstrip(b"\0").decode())
    for field_name in ["AddressOfEntryPoint", "ImageBase", "DllCharacteristics", "Subsystem"]:
        assert getattr(before.OPTIONAL_HEADER, field_name) == getattr(after.OPTIONAL_HEADER, field_name)
    for i in range(16):
        if i != 2:  # Resource directory size is expected to change.
            a, b = before.OPTIONAL_HEADER.DATA_DIRECTORY[i], after.OPTIONAL_HEADER.DATA_DIRECTORY[i]
            assert (a.VirtualAddress, a.Size) == (b.VirtualAddress, b.Size), (path.name, i)
    actual_fields = {}
    for group in after.FileInfo:
        for block in group:
            if block.Key == b"StringFileInfo":
                for table in block.StringTable:
                    actual_fields.update({k.decode(): v.decode() for k, v in table.entries.items()})
    for change in changes:
        assert actual_fields[change["field"]] == change["after"]
    return {"file": path.name, "changes": changes,
            "unchanged_sections": unchanged_sections,
            "other_resource_payloads_unchanged": True,
            "sha256_before": sha((SOURCE / path.name).read_bytes()),
            "sha256_after": sha(path.read_bytes())}


def read_pak(data: bytes):
    version, count, encoding = struct.unpack_from("<IIB", data)
    if version != 4 or encoding != 1:
        raise ValueError("Only the observed v4 UTF-8 packs are supported")
    table_end = 9 + 6 * (count + 1)
    rows = [struct.unpack_from("<HI", data, 9 + 6 * i) for i in range(count + 1)]
    assert rows[0][1] == table_end and rows[-1] == (0, len(data))
    ids = [rid for rid, _ in rows[:-1]]
    assert ids == sorted(set(ids))
    assert all(table_end <= a[1] <= b[1] <= len(data) for a, b in zip(rows, rows[1:]))
    return {rid: data[off:rows[i + 1][1]] for i, (rid, off) in enumerate(rows[:-1])}


def write_pak(items: dict[int, bytes]) -> bytes:
    offset = 9 + 6 * (len(items) + 1)
    table, chunks = [], []
    for rid, data in items.items():
        table.append(struct.pack("<HI", rid, offset))
        chunks.append(data)
        offset += len(data)
    return struct.pack("<IIB", 4, len(items), 1) + b"".join(table) + struct.pack("<HI", 0, offset) + b"".join(chunks)


def edit_pak(path: Path):
    original = path.read_bytes()
    items = read_pak(original)
    assert write_pak(items) == original  # Lossless original-format round trip.
    updated, changes = dict(items), []
    for rid, payload in items.items():
        if not 10000 <= rid <= 10090 or rid in CREDIT_IDS:
            continue
        before = payload.decode("utf-8")
        after = before.replace("Clover", "Sofiles")
        if before != after:
            updated[rid] = after.encode("utf-8")
            changes.append({"id": rid, "before": before, "after": after})
    assert changes
    output = write_pak(updated)
    reparsed = read_pak(output)
    assert reparsed == updated and reparsed.keys() == items.keys()
    for rid in items.keys() - {row["id"] for row in changes}:
        assert items[rid] == reparsed[rid]
    assert all(reparsed[rid] == b"Sofiles" for rid in [10000, 10001, 10002, 10018])
    if b"Clover" in items[10023]:
        assert "Sofiles" in reparsed[10023].decode("utf-8")
    for rid in [10011, 10012, 10013, 10014, 11329, 11330, 11332, 11333, 11334]:
        if rid in items:
            assert items[rid] == reparsed[rid]
    path.write_bytes(output)
    return {"file": str(path.relative_to(DEST)), "resource_count": len(items),
            "sha256_before": sha(original), "sha256_after": sha(output),
            "changes": changes, "all_other_payloads_unchanged": True}


def main():
    resume = sys.argv[1:] == ["--resume"]
    if sys.argv[1:] and not resume:
        raise ValueError("The only supported option is --resume")
    if DEST.exists() and not resume:
        raise FileExistsError(f"Refusing to overwrite existing preview: {DEST}")
    for name, digest in EXPECTED.items():
        assert sha((SOURCE / name).read_bytes()) == digest, name
    original_hashes = {str(p.relative_to(SOURCE)): sha(p.read_bytes())
                       for p in SOURCE.rglob("*") if p.is_file()}
    # Validate every pack before creating the output directory.
    packs = sorted((SOURCE / "locales").glob("*.pak"))
    assert len(packs) == 53
    for path in packs:
        assert write_pak(read_pak(path.read_bytes())) == path.read_bytes()
    if DEST.exists():
        assert DEST.resolve().is_relative_to((ROOT / "builds").resolve())
        allowed = {*EXPECTED, "License.txt", "README.md", "SHA256SUMS.txt",
                   *(str(Path("locales") / p.name) for p in packs)}
        for path in [DEST, *DEST.rglob("*")]:
            assert not path.is_symlink() and not path.is_junction(), str(path)
            if path.is_file():
                assert str(path.relative_to(DEST)) in allowed, str(path)
    DEST.mkdir(parents=True, exist_ok=resume)
    (DEST / "locales").mkdir(exist_ok=resume)
    for name in [*EXPECTED, "License.txt"]:
        shutil.copy2(SOURCE / name, DEST / name)
    for path in packs:
        shutil.copy2(path, DEST / "locales" / path.name)
    binaries = [edit_pe_version(DEST / name) for name in EXPECTED]
    locales = [edit_pak(DEST / "locales" / path.name) for path in packs]
    assert all(sha((SOURCE / name).read_bytes()) == digest for name, digest in original_hashes.items())
    (DEST / "README.md").write_text(
        "# Sofiles — copie de personnalisation 0.1\n\n"
        "Le nom Sofiles remplace Clover dans les libellés des 53 fichiers de langue "
        "et les propriétés de produit des quatre composants principaux. Les crédits "
        "d’origine sont conservés.\n\n"
        "Cette copie est destinée aux essais en environnement isolé. Elle n’est pas "
        "installée et ne constitue pas une version corrigée des vulnérabilités "
        "décrites dans ../../AUDIT_VULNERABILITES.md. Aucun setup historique n’est inclus.\n\n"
        "La compatibilité Windows 11 et les libellés effectivement affichés restent "
        "à vérifier à l’exécution. Aucun composant Clover n’a été exécuté ou enregistré "
        "sur le PC pour produire cette copie.\n\n"
        "Les noms de fichiers clover.exe et clover.dll ainsi que les identifiants "
        "internes restent ceux attendus par les composants d’origine. Il ne faut "
        "pas renommer ces fichiers manuellement. Des mentions Clover restent dans "
        "le code et les crédits. Aucun raccourci de lancement ni désinstalleur "
        "n’est fourni à cette étape.\n",
        encoding="utf-8")
    manifest = {str(p.relative_to(DEST)): sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    report = {"name": "Sofiles", "stage": "branding-preview-only", "output": str(DEST),
              "source_resource_evidence": "ev_a2f071a1d7972e7512d14e0bd9a8c50671c151bb44dc979f11bf90e6588b351c",
              "binaries": binaries, "locales": locales, "manifest_sha256": manifest,
              "checks": {"original_files_unchanged": len(original_hashes),
                         "locale_files": len(locales),
                         "localized_resources_changed": sum(len(row["changes"]) for row in locales),
                         "native_code_sections_unchanged": True,
                         "target_execution": False,
                         "shell_registration": False,
                         "runtime_validation": "not_performed",
                         "security_fixes": "not_included"},
              "format_references": [
                  "https://raw.githubusercontent.com/chromium/chromium/main/tools/grit/grit/format/data_pack.py",
                  "https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-updateresourcew",
                  "https://learn.microsoft.com/en-us/windows/win32/menurc/vs-versioninfo"]}
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "sofiles-branding.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DEST / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items())), encoding="utf-8")
    print(json.dumps({"output": str(DEST), "checks": report["checks"], "report": str(REPORT / "sofiles-branding.json")}))


if __name__ == "__main__":
    main()
