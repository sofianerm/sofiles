"""Exercise the real NSIS setup in workspace fixtures, without system integration."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import winreg

import build_sofiles_product as build

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def registry_snapshot():
    result = {}
    for path in [r'Software\Sofiles',r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles']:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as key:
                rows=[]; index=0
                while True:
                    try: rows.append(winreg.EnumValue(key,index));index+=1
                    except OSError: break
                result[path]=rows
        except FileNotFoundError: result[path]=None
    return result

def install(setup, destination, language):
    # NSIS requires /D last, without quotes even when the destination has spaces.
    command = '"'+str(setup)+'" /S /TESTMODE=1 /LANG='+language+' /D='+str(destination)
    completed=subprocess.run(command,timeout=90)
    if completed.returncode:
        error=destination/'setup-error.txt'
        raise RuntimeError('Installer failed (%s): %s'%(completed.returncode,error.read_text(errors='replace') if error.exists() else 'no diagnostic file'))

def main():
    report=json.loads((build.LOG/'build-report.json').read_text(encoding='utf-8'))
    run=(build.ROOT/'analysis/installer-tests'/uuid.uuid4().hex).resolve()
    assert run.is_relative_to(build.ROOT.resolve())
    run.mkdir(parents=True)
    registry_before=registry_snapshot()
    preferences=build.ROOT.home()/'AppData/Local/Sofiles/settings.json'
    profile_before=preferences.read_bytes() if preferences.exists() else None
    checks=[]
    for language in ['fr','en','de']:
        root=run/('Sofiles '+language)
        install(Path(report['setup']),root,language)
        runtime=root/'versions'/build.VERSION
        for name,digest in report['files'].items():
            path=runtime/name
            assert path.is_file(),name
            if not name.startswith('locales/'): assert sha(path)==digest,name
        assert (root/'Uninstall.exe').is_file()
        state=json.loads((runtime/'runtime-language.json').read_text())
        assert state['Language']==language and Path(state['Root'])==runtime
        profile=root/'test-user-data/settings.json'
        config=json.loads(profile.read_text());assert config['Language']==language
        config['AutomaticUpdates']=True;profile.write_text(json.dumps(config))
        favourite=root/'test-user-data/favourites.json';favourite.write_text('{"keep":"my folder"}')
        unknown=runtime/'user-note.txt';unknown.write_text('keep this file')
        install(Path(report['setup']),root,language)
        assert json.loads(profile.read_text())['AutomaticUpdates'] is True
        assert favourite.read_text()=='{"keep":"my folder"}'
        subprocess.run('"'+str(root/'Uninstall.exe')+'" /S _?='+str(root),check=True,timeout=60)
        assert not (runtime/'Sofiles.exe').exists()
        assert unknown.read_text()=='keep this file'
        assert favourite.read_text()=='{"keep":"my folder"}'
        assert profile.exists()
        checks.append({'language':language,'silent_install':True,'repair':True,'uninstall':True,'preferences_preserved':True,'unknown_file_preserved':True})
    assert registry_snapshot()==registry_before,'Test mode changed Windows registry'
    assert (preferences.read_bytes() if preferences.exists() else None)==profile_before,'Test mode changed user preferences'
    result={'version':build.VERSION,'installer':'NSIS 3.13','checks':checks,'real_registry_unchanged':True,'real_preferences_unchanged':True,'fixture':str(run)}
    (build.LOG/'installer-tests.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
