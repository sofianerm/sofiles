"""Run native byte-scope and product trust-boundary checks; no installation."""
import json
from pathlib import Path
import subprocess
import sys
import uuid
import build_sofiles_product as build

def main():
    report_file = build.LOG / 'build-report.json'
    report = json.loads(report_file.read_text(encoding='utf-8'))
    for name, digest in report['files'].items():
        assert build.native.base.sha((build.OUT / name).read_bytes()) == digest, name
    assert build.native.base.sha(Path(report['setup']).read_bytes()) == report['setup_sha256']
    native_names = [x['name'] for x in report['binaries']]
    # Explicit file arguments, no shell interpolation of user paths.
    ps = "$ErrorActionPreference='Stop'; $items = @(" + ','.join("'" + str(build.OUT / p).replace("'", "''") + "'" for p in native_names) + "); @($items | ForEach-Object { [Diagnostics.FileVersionInfo]::GetVersionInfo($_) } | Select-Object ProductName,CompanyName,FileVersion,ProductVersion,LegalCopyright) | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath '" + str(build.LOG / 'windows-version-info.json').replace("'", "''") + "'"
    subprocess.run(['powershell.exe','-NoProfile','-Command',ps],check=True)
    subprocess.run([sys.executable,str(build.ROOT/'tools/verify_sofiles_full.py'),str(report_file)],check=True)
    tests = build.LOG / 'SofilesTests.exe'
    build.compile_cs(tests,'Sofiles.Tests',build.LOG/'ProductConfig.cs',console=True,extras=[build.ROOT/'src/sofiles/Tests.cs'])
    run = subprocess.run([str(tests),str(build.ROOT/'analysis/product-test-fixtures'),str(build.OUT)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (build.LOG/'product-tests.json').write_text(run.stdout,encoding='utf-8')
    if run.returncode: raise RuntimeError(run.stdout + run.stderr)
    checks = json.loads(run.stdout)
    if report.get('installer_type')=='NSIS 3.13':
        subprocess.run([sys.executable,str(build.ROOT/'tools/test_sofiles_installer.py')],check=True,timeout=400)
    summary = {'checks_passed': len(checks), 'package_files_verified': len(report['files']),
               'native_files_verified':len(native_names), 'real_user_install':False,
               'installer_tests':str(build.LOG/'installer-tests.json')}
    (build.LOG/'test-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__ == '__main__': main()
