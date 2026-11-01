"""Independent bounds/byte-scope checks before launching the rebranded PE files."""
import json
from pathlib import Path
import struct
import sys

import build_sofiles as base
import pefile

ROOT = base.ROOT
report_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "analysis/branding/full-build/build-report.json"
report = json.loads(report_path.read_text(encoding="utf-8"))
version = report.get("version", "1.0.0")
out = Path(report["output"])
results = []
for item in report["binaries"]:
    original = pefile.PE(data=(base.SOURCE / item["original_name"]).read_bytes())
    current = pefile.PE(data=(out / item["name"]).read_bytes())
    patches = []
    for patch in item["native"]["pointer_changes"]:
        fmt = "<q" if patch["kind"] == "DIR64_absolute_pointer" else (
            "<i" if patch["kind"] == "RIP_relative_operand" else "<I")
        patches.append((patch["site_rva"], struct.pack(fmt, patch["value"])))
    for patch in item["native"]["literal_length_changes"]:
        patches.append((patch["site_rva"], patch["new"].to_bytes(patch["size"], "little")))
    sections = []
    for old_section in original.sections:
        name = old_section.Name.rstrip(b"\0").decode()
        new_section = next(s for s in current.sections if s.Name == old_section.Name)
        if name == ".rsrc":
            continue
        # Resource growth can move the relocation section. Its directory entry
        # must follow it; executable/data sections must retain their RVAs.
        if name == ".reloc":
            assert current.OPTIONAL_HEADER.DATA_DIRECTORY[5].VirtualAddress == new_section.VirtualAddress
        else:
            assert old_section.VirtualAddress == new_section.VirtualAddress, (item["name"], name)
        expected = bytearray(old_section.get_data())
        for rva, payload in patches:
            offset = rva - old_section.VirtualAddress
            if 0 <= offset < len(expected):
                assert offset + len(payload) <= len(expected)
                expected[offset:offset + len(payload)] = payload
        assert bytes(expected) == new_section.get_data(), (item["name"], name, "unexpected section byte changes")
        sections.append(name)
    old_exports = getattr(original, "DIRECTORY_ENTRY_EXPORT", None)
    new_exports = getattr(current, "DIRECTORY_ENTRY_EXPORT", None)
    if old_exports:
        assert [(s.name, s.ordinal, s.address) for s in old_exports.symbols] == [
            (s.name, s.ordinal, s.address) for s in new_exports.symbols]
        assert new_exports.name.decode() == item["name"]
    assert all(not (s.Characteristics & 0x20000000 and s.Characteristics & 0x80000000) for s in current.sections)
    assert current.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size == 0
    assert current.verify_checksum()
    assert current.OPTIONAL_HEADER.DllCharacteristics == original.OPTIONAL_HEADER.DllCharacteristics
    results.append({"file": item["name"], "sections_verified": sections,
                    "native_operand_patches": len(patches), "exports_preserved": True,
                    "checksum_valid": True, "dep_aslr_flags_preserved": True,
                    "no_rwx_section": True})

for name, digest in report["manifest_sha256"].items():
    assert base.sha((out / name).read_bytes()) == digest, name
for name, digest in base.EXPECTED.items():
    assert base.sha((base.SOURCE / name).read_bytes()) == digest, name
assert base.sha((out / "licenses/Clover-original.txt").read_bytes()) == base.sha((base.SOURCE / "License.txt").read_bytes())
versions = json.loads((report_path.parent / "windows-version-info.json").read_text(encoding="utf-8-sig"))
for entry in versions:
    assert entry["ProductName"] == "Sofiles"
    assert entry["CompanyName"] == ("Sofiane Messaoudi" if version in ["1.0.0", "1.1.0"] else "Sofiles")
    assert entry["FileVersion"] == version + ".0"
    assert entry["ProductVersion"] == version
    if version in ["1.0.0", "1.1.0"]:
        assert "EJIE" in entry["LegalCopyright"] and "Sofiane Messaoudi" in entry["LegalCopyright"]
    else:
        assert "Sofiles" in entry["LegalCopyright"] and "licenses/NOTICE.md" in entry["LegalCopyright"]
result = {"binaries": results, "files_manifest_verified": len(report["manifest_sha256"]),
          "windows_version_info_verified": len(versions), "original_licence_preserved": True}
(report_path.parent / "static-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
