"""Build Sofiles's personal native edition and the new managed product tools.

Requires the locally supplied original Clover files and the pinned inventories.
Never installs the resulting app or registers shell components.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import build_sofiles_full as native
import sofiles_product_content as content

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/product.json").read_text(encoding="utf-8"))
VERSION = CONFIG["version"]
assert re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", VERSION)
OUT = ROOT / "builds" / ("Sofiles-" + VERSION)
LOG = ROOT / "analysis/product-build"
DIST = ROOT / "dist"
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
REFERENCES = ["System.dll", "System.Core.dll", "System.Drawing.dll", "System.Windows.Forms.dll",
              "System.Web.Extensions.dll", "System.IO.Compression.dll", "System.IO.Compression.FileSystem.dll",
              "Microsoft.CSharp.dll", "System.Xml.dll"]

def config_source(path, payload_hash=""):
    fields = {"Version": VERSION, "Author": CONFIG["author"], "Email": CONFIG["email"],
              "DonationUrl": CONFIG["donation_url"], "ReleasesUrl": CONFIG["releases_url"],
              "ManifestUrl": CONFIG["manifest_url"], "PublicKey": CONFIG["update_public_key_xml"],
              "PayloadSha256": payload_hash}
    body = "\n".join("public const string %s = %s;" % (k, json.dumps(v, ensure_ascii=True)) for k, v in fields.items())
    path.write_text("namespace Sofiles { public static class ProductConfig {\n" + body + "\n} }", encoding="utf-8")

def compile_cs(output, main, config, payload=None, console=False, extras=()):
    assert CSC.exists(), "Windows .NET Framework C# compiler required"
    args = [str(CSC), "/nologo", "/optimize+", "/warn:4", "/utf8output", "/platform:anycpu",
            "/target:" + ("exe" if console else "winexe"), "/out:" + str(output), "/main:" + main,
            "/win32icon:" + str(ROOT / "assets/sofiles/sofiles.ico"),
            "/win32manifest:" + str(ROOT / "src/sofiles/app.manifest")]
    args += ["/r:" + name for name in REFERENCES]
    if payload: args += ["/resource:" + str(payload) + ",Sofiles.Payload"]
    args += [str(config), str(LOG / "AssemblyInfo.cs")]
    args += [str(ROOT / "src/sofiles" / n) for n in ("Common.cs", "InstallOps.cs")]
    args += [str(p) for p in extras]
    completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (LOG / (output.stem + "-compile.log")).write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)

def main():
    LOG.mkdir(parents=True, exist_ok=True); DIST.mkdir(exist_ok=True)
    native.VERSION = VERSION; native.OUT = OUT
    inventory = json.loads((ROOT / "analysis/branding/full-native/native-branding-inventory.json").read_text(encoding="utf-8"))
    fixups = json.loads((ROOT / "analysis/branding/full-native/length-fixups.json").read_text(encoding="utf-8"))["fixups"]
    for original, digest in native.base.EXPECTED.items():
        assert native.base.sha((native.SRC / original).read_bytes()) == digest
    records = []
    native_report = LOG / ('native-report-' + VERSION + '.json')
    if not OUT.exists():
        OUT.mkdir(parents=True)
        for directory in ["locales", "licenses", "assets"]: (OUT / directory).mkdir()
        shutil.copy2(native.SRC / "License.txt", OUT / "licenses/Clover-original.txt")
        for suffix in ["ico", "svg"]: shutil.copy2(ROOT / "assets/sofiles" / ("sofiles." + suffix), OUT / "assets" / ("sofiles." + suffix))
        for entry in inventory["files"]:
            for row in entry["native_strings"]:
                if row.get("proposed_replacement") is not None:
                    row["proposed_replacement"] = row["proposed_replacement"].replace("1.0.0", VERSION)
            original = entry["file"]; target = OUT / native.NAMES[original]
            shutil.copy2(native.SRC / original, target)
            resources = native.update_resources(target, original)
            changes = native.add_native_branding(target, entry, fixups)
            records.append({"original_name": original, "name": target.name, "resources": resources, "native": changes})
        (OUT/'CREDITS.md').write_text('# Sofiles\n\nTools: Sofiles contributors. Component notices: licenses/NOTICE.md.\n',encoding='utf-8')
        native_report.write_text(json.dumps({"version": VERSION, "output": str(OUT), "binaries": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        previous = json.loads((native_report if native_report.exists() else LOG / "native-report.json").read_text(encoding="utf-8"))
        assert previous["version"] == VERSION and previous["output"] == str(OUT)
        for item in previous["binaries"]:
            assert native.base.sha((OUT / item["name"]).read_bytes()) == item["native"]["sha256"], item["name"]
        records = previous["binaries"]
        if not native_report.exists(): native_report.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
    localization = content.build_content(OUT, VERSION)
    if (ROOT/'LICENSE').exists(): shutil.copy2(ROOT/'LICENSE',OUT/'licenses/Sofiles-tools-MIT.txt')
    nsis_notice=ROOT/'tools/nsis/nsis-3.13/COPYING'
    if nsis_notice.exists(): shutil.copy2(nsis_notice,OUT/'licenses/NSIS.txt')
    (LOG / "AssemblyInfo.cs").write_text(
        'using System.Reflection;\n[assembly: AssemblyTitle("Sofiles")]\n[assembly: AssemblyProduct("Sofiles")]\n'
        '[assembly: AssemblyCompany("Sofiles")]\n[assembly: AssemblyCopyright("Sofiles contributors. Component notices: licenses/NOTICE.md.")]\n'
        '[assembly: AssemblyVersion("' + VERSION + '.0")]\n[assembly: AssemblyFileVersion("' + VERSION + '.0")]\n', encoding="utf-8")
    config_source(LOG / "ProductConfig.cs")
    compile_cs(OUT / "SofilesSettings.exe", "Sofiles.Manager", LOG / "ProductConfig.cs", extras=[ROOT / "src/sofiles/Manager.cs"])
    app_config = '<?xml version="1.0"?><configuration><startup useLegacyV2RuntimeActivationPolicy="true"><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8"/></startup></configuration>'
    (OUT / "SofilesSettings.exe.config").write_text(app_config, encoding="utf-8")
    # Personal portable launch, including relocation-safe local documentation links.
    (OUT / "README.md").write_text(
        '# Sofiles ' + VERSION + '\n\nLancer SofilesSettings.exe pour les langues, l’aide et les mises à jour. '
        'Le raccourci Sofiles lance ce gestionnaire avec --launch. Fermer le moteur avec son menu Quitter avant un changement de langue.\n\n'
        'Contact : ' + CONFIG['email'] + '. Don PayPal facultatif : 20 CHF. Le compte destinataire doit être confirmé dans PayPal.\n\n'
        'Consulter licenses/NOTICE.md pour les composants. '
        'Les limites du moteur historique restent documentées dans les notices de cette préversion. '
        'Les rares messages natifs hors PAK restent en français.\n\n'
        'Installation par utilisateur ; désinstallation conserve favoris et profil. Mises à jour facultatives dans les réglages.\n', encoding='utf-8')
    files = {str(p.relative_to(OUT)).replace('\\','/'): native.base.sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.name not in ['SHA256SUMS.txt', 'First Run', 'runtime-language.json']}
    (OUT / "SHA256SUMS.txt").write_text(''.join(f'{v}  {k}\n' for k,v in sorted(files.items())), encoding='utf-8')
    payload = LOG / "payload.zip"
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file() and path.name not in ['First Run','runtime-language.json']: archive.write(path, str(path.relative_to(OUT)).replace('\\','/'))
    config_source(LOG / "ProductConfig.Setup.cs", native.base.sha(payload.read_bytes()))
    setup = DIST / f'Sofiles-Setup-{VERSION}.exe'
    helper = LOG / 'SofilesSetupHelper.exe'
    compile_cs(helper,'Sofiles.SetupHelper',LOG/'ProductConfig.cs',console=True,extras=[ROOT/'src/sofiles/SetupHelper.cs'])
    install_manifest = LOG/'install-files.txt'
    install_manifest.write_text(''.join('versions/'+VERSION+'/'+name+'\n' for name in sorted(files))+'versions/'+VERSION+'/SHA256SUMS.txt\n',encoding='utf-8')
    compiler = ROOT/'tools/nsis/nsis-3.13/makensis.exe'
    if not compiler.exists(): raise RuntimeError('NSIS 3.13 portable compiler required: tools/nsis/nsis-3.13/makensis.exe')
    command = [str(compiler),'/INPUTCHARSET','UTF8','/V3','/DPRODUCT_VERSION='+VERSION,'/DOUTPUT_EXE='+str(setup),'/DPAYLOAD_DIR='+str(OUT),
               '/DPRODUCT_ICON='+str(ROOT/'assets/sofiles/sofiles.ico'),'/DSETUP_HELPER='+str(helper),
               '/DINSTALL_MANIFEST='+str(install_manifest),str(ROOT/'installer/Sofiles.nsi')]
    compiled = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (LOG/'nsis-compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
    if compiled.returncode: raise RuntimeError(compiled.stdout+compiled.stderr)
    result = {"version": VERSION, "output": str(OUT), "setup": str(setup), "setup_sha256": native.base.sha(setup.read_bytes()),
              "payload_sha256": native.base.sha(payload.read_bytes()), "files": files, "languages": ["fr","en","de"],
              "binaries": records, "manifest_sha256": files,
              "updates_configured": bool(CONFIG['manifest_url'] and CONFIG['update_public_key_xml']),
              "installer_type":"NSIS 3.13", "installed_by_builder": False, "publicly_redistributed": False}
    (LOG / 'build-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['files','binaries','manifest_sha256']}))

if __name__ == '__main__': main()
