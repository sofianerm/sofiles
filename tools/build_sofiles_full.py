"""Build Sofiles 1.0.0 from the pinned originals; do not install or run it.

Resource changes use Windows UpdateResource. Native changes are limited to
inventoried string pointers, reviewed literal lengths and export-name RVAs.
All original files and original copyright/licence evidence are retained.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import json
from pathlib import Path
import re
import shutil
import struct
import sys

import build_sofiles as base
from PIL import Image
import pefile

ROOT = base.ROOT
SRC = base.SOURCE
OUT = ROOT / "builds/Sofiles-1.0.0"
LOG = ROOT / "analysis/branding/full-build"
NAMES = {"clover.exe": "Sofiles.exe", "clover.dll": "SofilesCore.dll",
         "TabHelper32.dll": "SofilesHelper32.dll", "TabHelper64.dll": "SofilesHelper64.dll"}
COPYRIGHT = "Personnalisation © 2026 Sofiane Messaoudi. Base Clover © EJIE Technology. Voir CREDITS.md."
VERSION = "1.0.0"


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def encoded(text, encoding):
    return text.encode("utf-16le" if encoding == "utf16le" else "ascii")


def version_tree(node, file_name):
    if node.key == "VS_VERSION_INFO":
        fixed = bytearray(node.value)
        assert len(fixed) == 52
        major, minor, patch = (int(v) for v in VERSION.split("."))
        for offset, value in [(8, major << 16 | minor), (12, patch << 16), (16, major << 16 | minor), (20, patch << 16)]:
            struct.pack_into("<I", fixed, offset, value)
        node.value = bytes(fixed)
    values = {
        "CompanyName": "Sofiane Messaoudi", "CompanyShortName": "Sofiane Messaoudi",
        "ProductName": "Sofiles", "ProductShortName": "Sofiles",
        "FileDescription": "Sofiles" if file_name.endswith(".exe") else
                           ("Sofiles — interface et onglets" if "Core" in file_name else "Sofiles — intégration à l’Explorateur"),
        "FileVersion": VERSION + ".0", "ProductVersion": VERSION,
        "InternalName": Path(file_name).stem, "OriginalFilename": file_name,
        "LegalCopyright": COPYRIGHT,
    }
    if node.kind == 1 and node.key in values:
        node.value = values[node.key].encode("utf-16le") + b"\0\0"
    for child in node.children:
        version_tree(child, file_name)


def icon_resources():
    image = Image.open(ROOT / "assets/sofiles/sofiles.ico")
    sizes = sorted(image.ico.sizes())
    payloads, directory = {}, bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
    for i, size in enumerate(sizes, 1001):
        bitmap = image.ico.getimage(size).convert("RGBA")
        stream = io.BytesIO()
        # PNG icon payloads keep the resource section compact on modern Windows.
        bitmap.save(stream, format="PNG")
        payloads[(3, i, 1033)] = stream.getvalue()
        width, height = size
        directory.extend(struct.pack("<BBBBHHIH", width % 256, height % 256, 0, 0,
                                     1, 32, len(stream.getvalue()), i))
    return payloads, bytes(directory)


def update_resources(path, original_name):
    pe = pefile.PE(data=path.read_bytes())
    originals = base.resources(pe)
    changes = {}
    for key, value in originals.items():
        if key[0] == 16:
            tree, _ = base.read_version(value)
            version_tree(tree, path.name)
            changes[key] = base.write_version(tree)
        elif key[0] == 24:
            # Preserve the assembly manifest's structure and execution level.
            value2 = value.replace(b"Clover", b"Sofiles").replace(b"clover", b"sofiles")
            value2 = value2.replace(b"3.0.406.0", (VERSION + ".0").encode("ascii"))
            if value2 != value:
                changes[key] = value2
        elif key[0] == "REGISTRY":
            # COM GUIDs stay consistent with the original compiled COM classes.
            value2 = value.replace(b"TabHelper.DLL", b"SofilesHelper.DLL")
            value2 = value2.replace(b"ExplorerWatcher Class", b"Sofiles Explorer Integration")
            value2 = value2.replace(b"TabExplorerHelper", b"Sofiles Explorer Helper")
            if value2 != value:
                changes[key] = value2
        elif key[0] == 5 and key[1] == 3000:
            from sofiles_dialog_resources import translate_dialog
            changes[key] = translate_dialog(value)
        elif key[0] == 6:
            from sofiles_dialog_resources import translate_string_block
            value2 = translate_string_block(value)
            if value2 != value:
                changes[key] = value2
    if original_name in ["clover.exe", "clover.dll"]:
        payloads, group = icon_resources()
        changes.update(payloads)
        changes[(14, "IDR_MAINFRAME" if original_name == "clover.exe" else 101, 1033)] = group
        for icon_id in range(1, 5):
            changes[(3, icon_id, 1033)] = None
    if original_name == "clover.dll":
        assert ("BINDATA", 6000, 0) in originals
        changes[("BINDATA", 6000, 0)] = (ROOT / "assets/sofiles/sofiles-about-190x145.png").read_bytes()

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    kernel.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                     wintypes.WORD, ctypes.c_void_p, wintypes.DWORD]
    kernel.UpdateResourceW.restype = wintypes.BOOL
    kernel.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
    kernel.EndUpdateResourceW.restype = wintypes.BOOL

    def rid(value):
        return ctypes.cast(ctypes.c_wchar_p(value), ctypes.c_void_p) if isinstance(value, str) else ctypes.c_void_p(value)

    handle = kernel.BeginUpdateResourceW(str(path), False)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        for (typ, name, lang), data in changes.items():
            buffer = ctypes.create_string_buffer(data) if data is not None else None
            if not kernel.UpdateResourceW(handle, rid(typ), rid(name), lang, buffer, len(data) if data else 0):
                raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.EndUpdateResourceW(handle, True)
        raise
    if not kernel.EndUpdateResourceW(handle, False):
        raise ctypes.WinError(ctypes.get_last_error())
    after = base.resources(pefile.PE(data=path.read_bytes()))
    expected = dict(originals)
    for key, value in changes.items():
        if value is None:
            expected.pop(key)
        else:
            expected[key] = value
    assert after == expected, path.name
    return {"modified_resource_keys": [list(k) for k in changes],
            "unmodified_resource_payloads_verified": len(originals.keys() - changes.keys())}


def add_native_branding(path, inventory, fixups):
    original = pefile.PE(data=(SRC / inventory["file"]).read_bytes())
    pe = pefile.PE(data=path.read_bytes())
    data = bytearray(path.read_bytes())
    pool = bytearray()
    targets = {}
    for row in inventory["native_strings"]:
        if row.get("proposed_replacement") is None or not row["references"] or row["section"] == ".rsrc":
            continue
        assert not row.get("non_relocation_exact_pointer_candidates"), row["text"]
        raw = encoded(row["text"], row["encoding"])
        assert original.get_data(row["rva"], len(raw)) == raw
        padding = align(len(pool), 4) - len(pool)
        pool.extend(b"\0" * padding)
        targets[row["offset"]] = {"row": row, "pool_offset": len(pool)}
        pool.extend(encoded(row["proposed_replacement"], row["encoding"]))
        pool.extend(b"\0\0" if row["encoding"] == "utf16le" else b"\0")
    assert targets
    section_rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                            for s in pe.sections), pe.OPTIONAL_HEADER.SectionAlignment)
    raw_offset = align(len(data), pe.OPTIONAL_HEADER.FileAlignment)
    raw_size = align(len(pool), pe.OPTIONAL_HEADER.FileAlignment)
    header_offset = pe.sections[-1].get_file_offset() + 40
    assert header_offset + 40 <= min(s.PointerToRawData for s in pe.sections)
    assert not any(data[header_offset:header_offset + 40])
    data.extend(b"\0" * (raw_offset - len(data)))
    data.extend(pool)
    data.extend(b"\0" * (raw_size - len(pool)))
    struct.pack_into("<8sIIIIIIHHI", data, header_offset, b".sfbrand", len(pool), section_rva,
                     raw_size, raw_offset, 0, 0, 0, 0, 0x40000040)
    struct.pack_into("<H", data, pe.FILE_HEADER.get_field_absolute_offset("NumberOfSections"), len(pe.sections) + 1)
    struct.pack_into("<I", data, pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage"),
                     align(section_rva + len(pool), pe.OPTIONAL_HEADER.SectionAlignment))
    struct.pack_into("<I", data, pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfInitializedData"),
                     pe.OPTIONAL_HEADER.SizeOfInitializedData + raw_size)
    pointer_changes, length_changes = [], []

    for target in targets.values():
        row = target["row"]
        new_rva = section_rva + target["pool_offset"]
        for ref in row["references"]:
            delta = ref.get("target_delta_bytes", 0)
            if delta:
                unit = 2 if row["encoding"] == "utf16le" else 1
                assert delta % unit == 0
                suffix = row["text"][delta // unit:]
                new_suffix = suffix.replace("CLOVER", "SOFILES").replace("Clover", "Sofiles").replace("clover", "sofiles")
                assert row["proposed_replacement"].count(new_suffix) == 1
                delta = len(encoded(row["proposed_replacement"].split(new_suffix)[0], row["encoding"]))
            site_rva = original.get_rva_from_offset(ref["site_offset"])
            site = pe.get_offset_from_rva(site_rva)
            kind = ref["kind"]
            if kind == "HIGHLOW_absolute_pointer":
                assert struct.unpack_from("<I", data, site)[0] == ref["old_pointer"]
                value = pe.OPTIONAL_HEADER.ImageBase + new_rva + delta
                struct.pack_into("<I", data, site, value)
            elif kind == "DIR64_absolute_pointer":
                assert struct.unpack_from("<Q", data, site)[0] == ref["old_pointer"]
                value = pe.OPTIONAL_HEADER.ImageBase + new_rva + delta
                struct.pack_into("<Q", data, site, value)
            elif kind == "RIP_relative_operand":
                assert ref["displacement_size"] == 4
                assert struct.unpack_from("<i", data, site)[0] == ref["old_displacement"]
                instruction_end_rva = ref["instruction_va"] - original.OPTIONAL_HEADER.ImageBase + ref["instruction_size"]
                value = new_rva + delta - instruction_end_rva
                struct.pack_into("<i", data, site, value)
            elif kind == "PE_export_module_name_RVA":
                assert struct.unpack_from("<I", data, site)[0] == ref["old_rva"]
                value = new_rva + delta
                struct.pack_into("<I", data, site, value)
            else:
                raise ValueError(f"Unsupported reference kind {kind}")
            pointer_changes.append({"site_rva": site_rva, "kind": kind,
                                    "new_target_rva": new_rva + delta, "value": value})

    for change in fixups:
        if change["file"] != inventory["file"] or change["target_string_offset"] not in targets:
            continue
        row = targets[change["target_string_offset"]]["row"]
        assert row["text"] == change["target_original_text"]
        site_rva = original.get_rva_from_offset(change["operand_offset"])
        site = pe.get_offset_from_rva(site_rva)
        size = change["operand_size"]
        assert data[site:site + size] == bytes.fromhex(change["old_operand_bytes_hex"])
        new_length = len(encoded(row["proposed_replacement"], row["encoding"])) // (2 if row["encoding"] == "utf16le" else 1)
        assert 0 < new_length < (128 if size == 1 else 0x80000000)
        data[site:site + size] = new_length.to_bytes(size, "little")
        length_changes.append({"site_rva": site_rva, "size": size, "old": change["old_length"],
                               "new": new_length, "target_original": row["text"]})

    # Recalculate the checksum and independently parse the finished PE.
    result = pefile.PE(data=bytes(data))
    struct.pack_into("<I", data, result.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), result.generate_checksum())
    path.write_bytes(data)
    result = pefile.PE(data=path.read_bytes())
    assert result.verify_checksum()
    assert result.OPTIONAL_HEADER.AddressOfEntryPoint == original.OPTIONAL_HEADER.AddressOfEntryPoint
    assert result.OPTIONAL_HEADER.DllCharacteristics == original.OPTIONAL_HEADER.DllCharacteristics
    assert result.FILE_HEADER.Machine == original.FILE_HEADER.Machine
    new_section = result.sections[-1]
    assert new_section.Name.rstrip(b"\0") == b".sfbrand" and new_section.Characteristics == 0x40000040
    # Existing relocation sites must still rebase every relocated absolute pointer.
    rebased = pefile.PE(data=path.read_bytes())
    relocated_base = result.OPTIONAL_HEADER.ImageBase + 0x1000000
    rebased.relocate_image(relocated_base)
    for change in pointer_changes:
        site = result.get_offset_from_rva(change["site_rva"])
        if change["kind"] == "HIGHLOW_absolute_pointer":
            assert rebased.get_dword_at_rva(change["site_rva"]) == relocated_base + change["new_target_rva"]
        elif change["kind"] == "DIR64_absolute_pointer":
            assert rebased.get_qword_at_rva(change["site_rva"]) == relocated_base + change["new_target_rva"]
        else:
            assert result.get_data(change["site_rva"], 4) == rebased.get_data(change["site_rva"], 4)
    return {"strings_redirected": len(targets), "pointer_changes": pointer_changes,
            "literal_length_changes": length_changes, "relocation_simulation_passed": True,
            "pool_rva": section_rva, "pool_bytes": len(pool), "sha256": base.sha(path.read_bytes())}


def write_locales():
    overrides = json.loads((ROOT / "analysis/branding/full-locales/fr-overrides.json").read_text(encoding="utf-8"))
    french = base.read_pak((SRC / "locales/fr.pak").read_bytes())
    for key, value in overrides.items():
        french[int(key)] = value.encode("utf-8")
    credits_uri = (OUT / "docs/credits.html").as_uri()
    help_uri = (OUT / "docs/help.html").as_uri()
    # Keep both link-marker pairs expected by the old About layout; both links
    # now lead to a real local credits page, never to the original donation URL.
    french[10013] = ("Personnalisation par BEGIN_LINK_CHRSofiane MessaoudiEND_LINK_CHR. "
                     "BEGIN_LINK_OSSCrédits et licencesEND_LINK_OSS.").encode("utf-8")
    french[10012] = "© 2026 Sofiane Messaoudi (personnalisation). Base Clover © EJIE Technology.".encode("utf-8")
    french[11168] = "Édition personnelle — mises à jour manuelles.".encode("utf-8")
    french[10090] = "Informations sur la version de &Sofiles".encode("utf-8")
    french[10081] = "Sofiles 1.0.0 — édition personnelle. Aucun canal de mise à jour configuré.".encode("utf-8")
    for rid in [11329, 11332, 11333]:
        french[rid] = credits_uri.encode("utf-8")
    french[11330] = help_uri.encode("utf-8")
    french[11334] = b""  # No vendor update feed for a personally modified build.
    paths = sorted((SRC / "locales").glob("*.pak"))
    rows = []
    for source in paths:
        original = base.read_pak(source.read_bytes())
        assert original.keys() == french.keys()
        updated = dict(original)
        # Leave low-level locale/font/layout settings alone. All visible UI
        # resource IDs use the reviewed French pack in this personal edition.
        for rid in updated:
            if rid >= 9500:
                updated[rid] = french[rid]
        blob = base.write_pak(updated)
        assert base.read_pak(blob) == updated
        assert b"Sofiles" == updated[10000]
        for rid, payload in updated.items():
            if rid >= 9500:
                assert not re.search("[\u3400-\u9fff]", payload.decode("utf-8")), (source.name, rid)
        destination = OUT / "locales" / source.name
        # Replace the directory entry atomically: a previously launched process
        # can still have the previous read-only PAK mapped into memory.
        temporary = destination.with_suffix(".pak.sofiles-tmp")
        temporary.write_bytes(blob)
        temporary.replace(destination)
        rows.append({"file": source.name, "resource_count": len(updated),
                     "changed_entries": sum(updated[k] != original[k] for k in updated),
                     "sha256": base.sha(blob)})
    return rows


def write_docs():
    (OUT / "docs").mkdir()
    credits = ("# Sofiles 1.0.0\n\nPersonnalisation par **Sofiane Messaoudi**.\n\n"
               "Copyright des modifications de personnalisation : © 2026 Sofiane Messaoudi.\n\n"
               "Sofiles est une édition personnelle modifiée de Clover 3.0.406, "
               "créé par EJIE Technology. Le code d’origine ne devient pas la propriété "
               "de l’auteur de cette personnalisation. Les mentions et la licence "
               "d’origine sont conservées dans licenses/Clover-original.txt.\n\n"
               "La base utilise des composants Chromium et des composants tiers. "
               "Leurs auteurs, droits et conditions restent applicables. Les sources "
               "originales complètes et toutes les notices de dépendances ne sont pas "
               "fournies dans l’archive historique ; aucun droit supplémentaire de "
               "redistribution n’est accordé par ce document.\n\n"
               "Version de cette édition : 1.0.0. Composants binaires d’origine : "
               "Clover 3.0.406.0. Aucun service public de mise à jour Sofiles n’est configuré.\n")
    (OUT / "CREDITS.md").write_text(credits, encoding="utf-8")
    html = ("<!doctype html><html lang='fr'><meta charset='utf-8'><title>Sofiles — Crédits</title>"
            "<style>body{font:17px/1.6 system-ui;max-width:720px;margin:60px auto;padding:0 24px;color:#17324d}"
            "h1{font-size:36px}a{color:#086a95}</style><h1>Sofiles 1.0.0</h1>"
            "<p>Personnalisation par <strong>Sofiane Messaoudi</strong>.</p>"
            "<p>© 2026 Sofiane Messaoudi pour les modifications de personnalisation.</p>"
            "<h2>Base et composants</h2><p>Base Clover 3.0.406, créé par EJIE Technology. "
            "Composants Chromium et tiers : leurs auteurs et licences respectifs restent reconnus.</p>"
            "<p><a href='../licenses/Clover-original.txt'>Licence d’origine de Clover</a> · "
            "<a href='../CREDITS.md'>Détail des crédits</a></p>"
            "<p>Cette édition personnelle n’est pas une réécriture du code d’origine.</p></html>")
    (OUT / "docs/credits.html").write_text(html, encoding="utf-8")
    (OUT / "docs/help.html").write_text(
        "<!doctype html><html lang='fr'><meta charset='utf-8'><title>Aide Sofiles</title>"
        "<h1>Sofiles 1.0.0</h1><p>Gestionnaire de fenêtres de l’Explorateur avec onglets et favoris.</p>"
        "<p>Cette édition personnelle a été essayée avec l’Explorateur classique activé par SwitchExplorer. "
        "La compatibilité avec l’interface moderne de Windows 11 n’est pas validée.</p>"
        "<p>Erreur SF-EXPLORER-001 : fermez Sofiles, vérifiez le mode classique de l’Explorateur "
        "et relancez l’application. Si le problème persiste, conservez le texte du message pour le diagnostic.</p>"
        "<p><a href='credits.html'>Crédits et licences</a></p></html>", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Sofiles 1.0.0\n\nPersonnalisation par Sofiane Messaoudi.\n\n"
        "Lanceur : Sofiles.exe. Interface de cette édition : français. "
        "Les fichiers SofilesCore.dll et SofilesHelper32/64.dll doivent rester avec le lanceur.\n\n"
        "Crédits : CREDITS.md ; licence d’origine : licenses/Clover-original.txt. "
        "Les sources et fichiers d’origine sont conservés séparément dans le dossier du projet.\n\n"
        "Cette édition modifie l’identité et les textes ; elle ne constitue pas une correction "
        "complète des vulnérabilités détaillées dans ../../AUDIT_VULNERABILITES.md. "
        "Aucun ancien setup ni désinstalleur historique n’est fourni. Aucun enregistrement "
        "de DLL ni changement de l’Explorateur n’est exécuté par la construction.\n\n"
        "Les liens d’aide/crédits de cette copie pointent vers docs/ dans ce dossier. "
        "Ils sont générés pour cet emplacement ; régénérer la copie après un déplacement.\n", encoding="utf-8")


def main():
    if OUT.exists():
        raise FileExistsError(f"Output already exists: {OUT}")
    inventory = json.loads((ROOT / "analysis/branding/full-native/native-branding-inventory.json").read_text(encoding="utf-8"))
    fixups = json.loads((ROOT / "analysis/branding/full-native/length-fixups.json").read_text(encoding="utf-8"))["fixups"]
    for name, digest in base.EXPECTED.items():
        assert base.sha((SRC / name).read_bytes()) == digest
    original_hashes = {str(p.relative_to(SRC)): base.sha(p.read_bytes()) for p in SRC.rglob("*") if p.is_file()}
    OUT.mkdir(parents=True)
    for directory in ["locales", "licenses", "assets"]:
        (OUT / directory).mkdir()
    shutil.copy2(SRC / "License.txt", OUT / "licenses/Clover-original.txt")
    for suffix in ["ico", "svg"]:
        shutil.copy2(ROOT / "assets/sofiles" / f"sofiles.{suffix}", OUT / "assets" / f"sofiles.{suffix}")
    records = []
    for entry in inventory["files"]:
        source_name = entry["file"]
        target = OUT / NAMES[source_name]
        shutil.copy2(SRC / source_name, target)
        resource_changes = update_resources(target, source_name)
        native_changes = add_native_branding(target, entry, fixups)
        records.append({"original_name": source_name, "name": target.name,
                        "resources": resource_changes, "native": native_changes})
    write_docs()
    locales = write_locales()
    assert all(base.sha((SRC / name).read_bytes()) == value for name, value in original_hashes.items())
    manifest = {str(p.relative_to(OUT)): base.sha(p.read_bytes()) for p in OUT.rglob("*") if p.is_file()}
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items())), encoding="utf-8")
    report = {"name": "Sofiles", "version": "1.0.0", "author_of_modifications": "Sofiane Messaoudi",
              "output": str(OUT), "binaries": records, "locales": locales, "manifest_sha256": manifest,
              "originals_verified_unchanged": len(original_hashes), "runtime_validation": "pending",
              "complete_security_remediation": False, "installed_or_registered_by_builder": False}
    LOG.mkdir(parents=True, exist_ok=True)
    (LOG / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "files": len(manifest), "binaries": len(records),
                      "localized_packs": len(locales), "report": str(LOG / "build-report.json")}))


if __name__ == "__main__":
    main()
