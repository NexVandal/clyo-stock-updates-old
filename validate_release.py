from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

def fail(msg): print(f"ERREUR: {msg}", file=sys.stderr); raise SystemExit(1)
def version_in(path, pattern):
    text=Path(path).read_text(encoding='utf-8-sig')
    m=re.search(pattern,text)
    return m.group(1) if m else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--version',required=True); ap.add_argument('--phase',choices=['source','built'],default='source'); ap.add_argument('--installer')
    a=ap.parse_args(); v=a.version.lstrip('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+',v): fail('version attendue au format X.Y.Z')
    checks={
      'app.py': version_in('app.py',r'APP_VERSION\s*=\s*["\']([^"\']+)'),
      'updater': version_in('CLYO_Stock_Updater.py',r'UPDATER_VERSION\s*=\s*["\']([^"\']+)'),
    }
    for name,found in checks.items():
      if found!=v: fail(f'{name}: version {found!r}, attendu {v!r}')
    iss=Path('CLYO_Stock_Installer.iss').read_text(encoding='utf-8-sig')
    if f'#define MyAppVersion "{v}"' not in iss: fail('version par défaut Inno Setup incohérente')
    required=['app.py','run_app.py','CLYO_Stock_Updater.py','CLYO_Stock_Builder.py','CLYO_Stock_Installer.iss','requirements.txt','assets/app_icon.ico']
    for f in required:
      if not Path(f).exists(): fail(f'fichier obligatoire absent: {f}')
    if v=='8.3.12': fail('règle projet: après 8.3.11, utiliser 9.0.0 et non 8.3.12')
    if a.phase=='built':
      if not a.installer or not Path(a.installer).is_file(): fail('installateur absent')
      if not Path('dist/CLYO_Stock_PORTABLE/CLYO_Stock.exe').is_file(): fail('EXE portable absent')
    print(f'Validation OK pour {v} ({a.phase})')
if __name__=='__main__': main()
