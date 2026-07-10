from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--version',required=True); ap.add_argument('--installer',required=True); ap.add_argument('--repository',required=True); ap.add_argument('--changelog',default='Mise à jour de CLYO Stock Atelier.')
 a=ap.parse_args(); v=a.version.lstrip('v'); p=Path(a.installer); sha=hashlib.sha256(p.read_bytes()).hexdigest()
 data={'latest_version':v,'installer_url':f'https://github.com/{a.repository}/releases/download/v{v}/{p.name}','asset_type':'installer_exe','sha256':sha,'mandatory':False,'published_at':datetime.now(timezone.utc).isoformat(),'changelog':[x.strip() for x in a.changelog.split('|') if x.strip()]}
 Path('version.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
