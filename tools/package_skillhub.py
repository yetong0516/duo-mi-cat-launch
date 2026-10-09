#!/usr/bin/env python3
"""Build a Tencent SkillHub metadata adapter without modifying canonical SKILL.md."""
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',default='0.1.0')
    p.add_argument('--out',required=True)
    p.add_argument('--homepage',default='https://github.com/yetong0516/duo-mi-cat-launch')
    a=p.parse_args()
    number=r'(?:0|[1-9]\d*)'
    prerelease=r'(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)'
    semver=number+r'\.'+number+r'\.'+number+r'(?:-'+prerelease+r'(?:\.'+prerelease+r')*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'
    if not re.fullmatch(semver,a.version):
        p.error('version must be valid SemVer')
    target=Path(a.out).resolve()/('duo-mi-cat-launch-skillhub-'+a.version)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():p.error('output already exists; choose another directory')
    target.mkdir()
    for name in ['SKILL.md','agents','assets','scripts','references']:
        source=ROOT/name
        if source.is_dir():shutil.copytree(source,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
        else:shutil.copy2(source,target/name)
    skill=target/'SKILL.md';text=skill.read_text(encoding='utf-8')
    extra='slug: duo-mi-cat-launch\nversion: '+a.version+'\ndisplayName: "Duo Mi 猫咪发布会"\nsummary: "多角度猫咪照片生成A14与B14发布会，保留原片背景并加配乐与渐变字卡"\ntags: [video, cat, creative, macos, seedance]\nhomepage: '+json.dumps(a.homepage)+'\n'
    text=text.replace('---\n','---\n'+extra,1);skill.write_text(text,encoding='utf-8')
    archive=Path(str(target)+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(target.rglob('*')):
            if file.is_file():z.write(file,arcname=str(file.relative_to(target)))
    print(json.dumps({'directory':str(target),'archive':str(archive),'slug':'duo-mi-cat-launch','version':a.version,'published':False},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
