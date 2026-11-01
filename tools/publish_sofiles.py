"""Publish this project's reviewed release through the existing Git login.

The GitHub connector has no repository visibility or Releases write endpoint.
No token is printed or saved by this script. Publication is an explicit mode.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REPO='sofianerm/sofiles'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['status','draft','upload','publish'])
    parser.add_argument('--body-file',type=Path)
    parser.add_argument('--asset',type=Path,action='append',default=[])
    args=parser.parse_args()
    config=json.loads((ROOT/'config/product.json').read_text(encoding='utf-8'))
    tag='v'+config['version']
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\nusername=sofianerm\n\n',text=True,capture_output=True,
        env=dict(os.environ,GCM_INTERACTIVE='Never',GIT_TERMINAL_PROMPT='0'),timeout=30)
    credential=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    token=credential.get('password')
    if result.returncode or not token:sys.exit('GitHub credential unavailable; nothing published.')
    def api(method,path,data=None,raw=None):
        url=path if path.startswith('https://') else 'https://api.github.com'+path
        if urllib.parse.urlsplit(url).hostname not in ['api.github.com','uploads.github.com']:raise ValueError('Unexpected GitHub endpoint')
        request=urllib.request.Request(url,method=method,
            data=raw if raw is not None else json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'Sofiles-release',
                     'Content-Type':'application/octet-stream' if raw is not None else 'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=90) as response:
                body=response.read();return response.status,json.loads(body) if body else {}
        except urllib.error.HTTPError as error:return error.code,{}
    status,repo=api('GET','/repos/'+REPO)
    if status!=200:sys.exit('Repository unavailable (HTTP %s).'%status)
    status,release=api('GET','/repos/'+REPO+'/releases/tags/'+tag)
    if args.mode=='draft' and status==404:
        if not args.body_file:sys.exit('--body-file required')
        status,release=api('POST','/repos/'+REPO+'/releases',{'tag_name':tag,'target_commitish':'main','name':'Sofiles '+config['version'],
            'body':args.body_file.read_text(encoding='utf-8'),'draft':True,'prerelease':True})
    if args.mode in ['draft','upload','publish'] and status not in [200,201]:sys.exit('Release request failed (HTTP %s).'%status)
    if args.mode=='upload':
        if not release.get('draft'):sys.exit('Assets on a published release will not be replaced.')
        existing={asset['name']:asset for asset in release.get('assets',[])}
        for path in args.asset:
            path=path.resolve()
            if not path.is_relative_to(ROOT.resolve()) or path.is_relative_to((ROOT/'.private').resolve()) or not path.is_file() or path.name.endswith(('.dpapi','.xml.private')):raise ValueError('Unapproved asset path')
            data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
            old=existing.get(path.name)
            if old:
                if old.get('digest')=='sha256:'+digest:continue
                code,_=api('DELETE','/repos/'+REPO+'/releases/assets/'+str(old['id']))
                if code!=204:sys.exit('Draft asset cleanup failed.')
            url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(path.name)
            code,asset=api('POST',url,raw=data)
            if code!=201 or (asset.get('digest') and asset['digest']!='sha256:'+digest):sys.exit('Asset upload failed or digest mismatch.')
            print(json.dumps({'uploaded':path.name,'sha256':digest,'bytes':len(data)}))
    if args.mode=='publish':
        if not release.get('assets'):sys.exit('Release has no assets.')
        if repo.get('private'):
            code,repo=api('PATCH','/repos/'+REPO,{'private':False,'description':'Onglets, favoris et réglages pour l’Explorateur Windows.','homepage':'https://github.com/'+REPO})
            if code!=200 or repo.get('private'):sys.exit('Repository visibility change failed.')
        code,release=api('PATCH','/repos/'+REPO+'/releases/'+str(release['id']),{'draft':False,'prerelease':True})
        if code!=200 or release.get('draft'):sys.exit('Release publication failed.')
    print(json.dumps({'repository':repo.get('html_url'),'private':repo.get('private'),'tag':tag,'release':release.get('html_url'),
        'draft':release.get('draft'),'prerelease':release.get('prerelease'),'assets':[a['name'] for a in release.get('assets',[])]}))

if __name__=='__main__':main()
