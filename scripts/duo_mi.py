#!/usr/bin/env python3
"""Prepare cat-launch generation inputs and run conservative local post-production."""
import argparse
import array
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

SKILL = Path(__file__).resolve().parent.parent
ROLES = {"face_front":"正面脸/眼鼻身份", "body_front":"正面全身/体型/胸爪",
         "body_left":"左侧全身与花纹", "body_right":"右侧全身与花纹",
         "body_side":"清楚侧面，侧别未确定", "body_back":"背部毛色与尾巴",
         "detail":"毛色/爪尾细节", "portrait":"补充肖像", "hug":"拥抱动作备用", "toy":"逗猫棒动作备用"}
ORDER = list(ROLES)

class TaskError(Exception):
    pass

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

def path_from(base, value):
    path = Path(value).expanduser()
    return (base/path if not path.is_absolute() else path).resolve()

def command(argv):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True)
    if result.returncode:
        raise TaskError((result.stderr or result.stdout or "Command failed")[-5000:])
    return result.stdout

def native(name, args, work):
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        raise TaskError("自带后期profile需要macOS和Swift/AVFoundation；其他系统请使用其现有视频工具执行同一原片流程。")
    source = SKILL/"scripts"/(name+".swift")
    cache = Path(work)/"compiled"; cache.mkdir(parents=True, exist_ok=True)
    binary = cache/(name+"-"+sha(source)[:12])
    if not binary.exists():
        command(["swiftc", "-parse-as-library", source, "-o", binary])
    return command([binary, *args])

def probe(path, report, work, frames=None, step=.5):
    args = [Path(path).resolve(), Path(report).resolve()]
    if frames is not None:
        Path(frames).mkdir(parents=True, exist_ok=True)
        args += [Path(frames).resolve(), step]
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    native("probe", args, work)
    return read(report)

def video_ok(data, tolerance=.25):
    if data.get("videoTracks", 0) != 1 or not data.get("frames"):
        raise TaskError("输入未包含可解码的单一视频轨。")
    if abs(data["videoDurationSeconds"]-14) > tolerance:
        raise TaskError(f"片段视频时长{data['videoDurationSeconds']:.3f}s，要求约14s；不能悄悄裁切或调速。")
    if abs(data["width"]/data["height"]-16/9) > .005:
        raise TaskError("片段不是16:9横屏；请处理当前生成参数，不能静默裁切。")

def prompt(package, segment):
    manifest = read(package/"manifest.json")
    selected = manifest["staged_photos"]
    roles = "; ".join(f"图{i+1}：{ROLES[p['role']]}" for i,p in enumerate(selected))
    seen = {p["role"] for p in selected}
    views = "只展示本次照片覆盖的视角。"
    if not {"body_left", "body_right"}.issubset(seen):
        views += "未完整提供左右两侧，不镜像，不编造另一侧毛色；只展示已给侧面。"
    if "body_back" not in seen:
        views += "没有背面照片，不做背部亮相。"
    continuity = manifest.get("continuity")
    if continuity:
        roles += f"; 图{len(selected)+1}：A末帧，只锁定接缝机位/光线/姿态，不替代身份"
        note = f"图{len(selected)+1}为实际A末帧。以它接续同机位、同光线、同猫和羽毛位置，前爪已抬，不从头重演。身份仍以前面实拍图为准。"
    else:
        note = "B尚未准备完成：A成功下载核验后，补真实末帧参考再提交B，不得现在同时发两段。"
    variables = dict(MODEL=manifest.get("model", "Seedance 2.0"), CAT_NAME=manifest["cat_name"],
                     SEGMENT=segment, CASH_BUDGET=manifest.get("cash_budget_rmb",0),
                     QUOTA_NOTE=manifest.get("quota_note", "仅使用本次任务已授权额度，不购买、充值或续订。"),
                     IDENTITY=manifest["identity_description"], PHOTO_ROLES=roles,
                     VIEW_COVERAGE=views, CONTINUITY=note,
                     LOOKS="、".join(manifest["looks"]),
                     LOOK_COUNT="一二三四五六"[len(manifest["looks"])-1],
                     INTERACTION_LOOKS=(manifest["looks"][1]+"与"+manifest["looks"][2]) if len(manifest["looks"])>=3 else "同一猫的两只视觉复制体")
    text = Template((SKILL/"assets"/(segment+"_prompt.txt")).read_text()).substitute(variables)
    if "body_back" not in seen:
        text = text.replace("展示已知侧身与背部", "只展示已知侧面").replace("轻转已知侧面与背部", "轻转已知侧面")
    if not seen.intersection({"body_left","body_right","body_side"}):
        text = text.replace("抬前爪后低空轻转", "正面抬爪与轻歪头").replace("只展示已知侧面", "保持正面展示")
    if segment=="B" and len(manifest["looks"])==1:
        text=text.replace("恰好一只同一猫并排，从左到右：", "单只该猫展示唯一造型：")
        text=text.replace("俯视同一只放射圆形编排，轻柔绕中心小角度转动，不高速旋转、不碰撞，造型保持。", "单猫正面或已知侧面轻巧展示与摆尾，上方留白，造型保持。")
        text=text.replace("同一款完整并排", "单只该造型猫展示")
    (package/(segment+"_14s_prompt.txt")).write_text(text, encoding="utf-8")

def prepare(args):
    source = Path(args.manifest).resolve(); base = source.parent
    manifest = read(source); package = Path(args.out).resolve()
    name = str(manifest.get("cat_name") or "小猫").strip()
    if len(name)>24 or "\n" in name:
        raise TaskError("猫名须为单行，建议短名；过长名字需要先规划文字留白。")
    identity = str(manifest.get("identity_description") or "").strip()
    if not identity:
        raise TaskError("请先读实拍图填写identity_description；不让模板猜测猫的外貌。")
    photos = manifest.get("photos", [])
    if len(photos)<4 and not manifest.get("allow_incomplete_photos", False):
        raise TaskError("通常至少4张照片：脸、全身、侧面、背面。用户明确限定更少图时可填allow_incomplete_photos并记录缺失视角。")
    seen_paths, hashes = set(), set()
    for item in photos:
        if item.get("role") not in ROLES:
            raise TaskError("未知照片角色: "+str(item.get("role")))
        path = path_from(base,item["path"])
        if not path.is_file(): raise TaskError("照片不存在: "+str(path))
        fingerprint = sha(path)
        if path in seen_paths or fingerprint in hashes:
            raise TaskError("重复同一照片不能冒充额外角度: "+str(path))
        seen_paths.add(path); hashes.add(fingerprint); item["path"] = str(path)
    seen_roles = {p["role"] for p in photos}
    missing = []
    if "face_front" not in seen_roles: missing.append("正面脸")
    if "body_front" not in seen_roles: missing.append("正面全身")
    if not seen_roles.intersection({"body_left","body_right","body_side"}): missing.append("侧面")
    if missing and not manifest.get("allow_incomplete_photos",False):
        raise TaskError("缺少身份关键角度: "+"、".join(missing))
    if not {"body_left","body_right"}.issubset(seen_roles): missing.append("左右全身侧面未齐：只展示已提供一侧")
    if "body_back" not in seen_roles: missing.append("背面：本次省略背部镜头")
    looks = manifest.get("looks") or read(SKILL/"assets/manifest-template.json")["looks"]
    if not 1<=len(looks)<=6: raise TaskError("looks需为1–6个造型；默认五款，按用户当次要求填写。")
    package.mkdir(parents=True,exist_ok=True); inputs=package/"inputs";inputs.mkdir(exist_ok=True)
    selected=[]
    for role in ORDER:
        candidate=next((p for p in photos if p["role"]==role),None)
        if candidate is not None: selected.append(candidate)
    maximum=int(manifest.get("maximum_identity_images",6))
    if not 2<=maximum<=8: raise TaskError("maximum_identity_images需为2–8，依据当次平台限制填写，并给B末帧预留一张。")
    selected=selected[:maximum]
    for candidate in sorted(photos,key=lambda p:ORDER.index(p["role"])):
        if len(selected)>=maximum: break
        if candidate not in selected: selected.append(candidate)
    staged=[]
    for i,item in enumerate(selected):
        src=Path(item["path"]);extension=src.suffix.lower()
        destination=inputs/f"{i+1:02d}_{item['role']}{extension}"
        if extension in {".heic", ".heif"}:
            if sys.platform!="darwin": raise TaskError("HEIC请先转成平台支持的JPEG/PNG，不改变身份或背景。")
            destination=destination.with_suffix(".jpg")
            command(["sips","-s","format","jpeg",src,"--out",destination])
        else: shutil.copy2(src,destination)
        staged.append({"role":item["role"],"file":str(destination.relative_to(package)),"sha256":sha(destination)})
    manifest.update(cat_name=name,identity_description=identity,looks=looks,staged_photos=staged,missing_views=missing)
    music=manifest.get("music_path")
    if music:
        src=path_from(base,music)
        if not src.is_file(): raise TaskError("配乐不存在: "+str(src))
        folder=package/"music";folder.mkdir(exist_ok=True);dest=folder/("user_music"+src.suffix.lower());shutil.copy2(src,dest)
        manifest["music_path"]=str(dest.relative_to(package));manifest["music_sha256"]=sha(dest)
    save(package/"manifest.json",manifest);save(package/"photos.json",staged)
    save(package/"status.json",{"phase":"prepared","A":"not_submitted","B":"waiting_for_A_last_frame","generation_performed_by_script":False,"missing_views":missing})
    prompt(package,"A");prompt(package,"B")
    captions=read(SKILL/"assets/captions-template.json")
    for caption in captions: caption["text"]=Template(caption["text"]).substitute(CAT_NAME=name,LOOK_COUNT="一二三四五六"[len(looks)-1])
    save(package/"captions.draft.json",captions)
    save(package/"style.json",read(SKILL/"assets/style.json"))
    return {"package":str(package),"identity_images_selected":len(staged),"missing_views":missing,"status":"prepared_only"}

def continuity(args):
    package=Path(args.package).resolve();manifest=read(package/"manifest.json")
    work=package/"work";work.mkdir(exist_ok=True)
    a=Path(args.a).resolve();data=probe(a,work/"A-media.json",work);video_ok(data)
    number=len(manifest["staged_photos"])+1;frame=package/"inputs"/f"{number:02d}_A_last_frame.png"
    native("frame",[a,data["lastFrameSeconds"]+.00001,frame],work)
    manifest["continuity"]={"file":str(frame.relative_to(package)),"source":str(a),"source_sha256":sha(a),"actualLastFrameSeconds":data["lastFrameSeconds"]}
    save(package/"manifest.json",manifest);prompt(package,"B")
    state=read(package/"status.json");state.update(A="media_verified",A_visual_qa="pending",B="prepared_with_continuity");save(package/"status.json",state)
    return {"frame":str(frame),"b_prompt":str(package/"B_14s_prompt.txt"),"A_visual_qa":"pending"}

def inspect(args):
    directory=Path(args.out).resolve();directory.mkdir(parents=True,exist_ok=True)
    data=probe(args.input,directory/"media.json",directory,directory/"frames",args.step)
    return {k:data.get(k) for k in ["file","durationSeconds","width","height","fps","frames","candidateCuts"]}

def pcm(path):
    values=array.array("h");values.frombytes(Path(path).read_bytes())
    if sys.byteorder!="little": values.byteswap()
    return values

def audio_check(reference,final,work):
    ref=work/"music-reference.raw";out=work/"music-export.raw"
    native("decode_audio",[reference,ref],work);native("decode_audio",[final,out],work)
    a,b=pcm(ref),pcm(out);n=min(len(a),len(b))
    if n<88200: raise TaskError("最终音频太短，无法核验。")
    exact=len(a)>=len(b) and a[:len(b)]==b
    if exact: return {"exactDecodedSamples":True,"sampleRate":44100,"outputFrames":len(b)//2,"timeOffsetSeconds":0}
    # Compare a stable internal excerpt, searching at most 1024 samples of encoder priming.
    start=88200;stop=min(n-4096,start+352800)
    def correlation(lag):
        x=[float(a[i]) for i in range(start,stop,32)]
        y=[float(b[i+lag]) for i in range(start,stop,32)]
        xy=sum(v*u for v,u in zip(x,y));xx=sum(v*v for v in x);yy=sum(v*v for v in y)
        return xy/math.sqrt(max(1,xx*yy))
    lag=max(range(-2048,2049,32),key=correlation);score=correlation(lag)
    if score<.995: raise TaskError(f"音乐信号不匹配，相关性{score:.4f}；不能宣称原曲已正确合入。")
    return {"exactDecodedSamples":False,"sampleRate":44100,"signalCorrelation":score,"measuredInterleavedSampleOffset":lag,"timeOffsetSeconds":lag/(44100*2)}

def assemble(args):
    output=Path(args.out).resolve();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() and not args.overwrite: raise TaskError("输出已存在；选新文件名或明确--overwrite。")
    a,b=Path(args.a).resolve(),Path(args.b).resolve()
    if output in {a,b}: raise TaskError("不能覆盖源片段。")
    pa=probe(a,work/"A-media.json",work);pb=probe(b,work/"B-media.json",work)
    video_ok(pa,args.tolerance);video_ok(pb,args.tolerance)
    if (pa["width"],pa["height"],pa["identityTransform"]) != (pb["width"],pb["height"],pb["identityTransform"]):
        raise TaskError("两段尺寸/方向不一致，不自动缩放或裁切。")
    if not pa["identityTransform"]: raise TaskError("此执行profile不静默旋转原片。请先处理用户明确选择的方向。")
    expected=pa["videoDurationSeconds"]+pb["videoDurationSeconds"]
    music=None;original_music=None;music_converted=False
    if args.music:
        original_music=Path(args.music).resolve();mp=probe(original_music,work/"music-media.json",work)
        if output==original_music: raise TaskError("不能覆盖用户原配乐。")
        if mp.get("audioTracks",0)<1: raise TaskError("指定配乐没有音频轨。")
        if mp["audioDurationSeconds"]<expected-.15: raise TaskError("指定音乐短于视频主体；不要自动换曲或循环。")
        music=original_music
        if mp.get("audioFormatID")!=1633772320:
            music=work/"music-aac.m4a";native("audio_aac",[original_music,music],work);music_converted=True
    raw=work/"original-assembly.mp4"
    native("concat",[a,b,music or "-",raw,work/"concat.json"],work)
    native("digest",[a,b,raw,work/"video-passthrough.json"],work)
    title_report=None
    if args.captions:
        captions=Path(args.captions).resolve();style=Path(args.style).resolve() if args.style else SKILL/"assets/style.json"
        if output in {captions,style}: raise TaskError("不能覆盖字幕或样式源文件。")
        caption_data=read(captions)
        for item in caption_data:
            if item.pop("end_at_video_end",False): item["end"]=expected
        captions=work/"captions.resolved.json";save(captions,caption_data)
        titled=work/"captioned-silent.mp4"
        native("captions",[raw,titled,captions,work/"caption-qa",work/"captions-report.json",style],work)
        title_report=read(work/"captions-report.json")
        if music: native("mux",[titled,music,output,work/"mux.json"],work)
        else: shutil.copy2(titled,output)
    else: shutil.copy2(raw,output)
    final=probe(output,work/"final-media.json",work,work/"final-qa",2)
    if abs(final["videoDurationSeconds"]-expected)>.02 or final["frames"]!=pa["frames"]+pb["frames"]:
        raise TaskError("后期改变了源视频时长或帧数，请检查导出。")
    if final["audioTracks"]!=(1 if music else 0): raise TaskError("最终音轨数量不正确。")
    verification=audio_check(original_music,output,work) if music else None
    report={"final":str(output),"durationSeconds":final["durationSeconds"],"resolution":[final["width"],final["height"]],"frames":final["frames"],"audioTracks":final["audioTracks"],"sources":[{"file":str(p),"sha256":sha(p)} for p in [a,b]],"musicSource":str(original_music) if music else None,"musicConvertedToAAC":music_converted,"musicVerification":verification,"captionsApplied":bool(args.captions),"captionReport":title_report,"backgroundReplaced":False,"speedChanged":False,"cropOrResizeApplied":False,"voiceoverAdded":False,"generation_performed_by_script":False,"technical_qa":"passed","visual_qa":"pending","final_sha256":sha(output)}
    save(output.with_suffix(".verification.json"),report)
    return {"final":str(output),"technical_qa":"passed","visual_qa":"pending","qa_directory":str(work/"final-qa"),"caption_qa":str(work/"caption-qa") if args.captions else None}

def music_cues(args):
    try: import numpy as np
    except ImportError: raise TaskError("可选music-cues命令需要NumPy；不影响素材包、生成与后期。")
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    data=probe(args.input,out/"music-media.json",out)
    if data.get("audioTracks",0)<1 or data["audioDurationSeconds"]<args.seconds:
        raise TaskError("原音缺失或短于分析区间。")
    native("decode_audio",[Path(args.input).resolve(),out/"music.raw"],out)
    audio=np.fromfile(out/"music.raw",dtype="<i2").reshape(-1,2).mean(axis=1)[:round(args.seconds*44100)]/32768
    audio=audio[::2];sr=22050;window=1024;hop=220;last=None;times=[];novelty=[]
    for start in range(0,len(audio)-window,hop):
        spectrum=np.abs(np.fft.rfft(audio[start:start+window]*np.hanning(window)))
        flux=0 if last is None else float(np.maximum(0,np.log1p(spectrum)-np.log1p(last)).sum())
        times.append((start+window/2)/sr);novelty.append(flux);last=spectrum
    threshold=float(np.quantile(novelty,.8));peaks=[]
    candidates=[i for i in range(1,len(novelty)-1) if novelty[i]>threshold and novelty[i]>=novelty[i-1] and novelty[i]>=novelty[i+1]]
    for i in sorted(candidates,key=lambda i:novelty[i],reverse=True):
        if all(abs(times[i]-times[j])>.28 for j in peaks): peaks.append(i)
    rows=[{"musicSeconds":times[i],"referenceFrame":round(times[i]*args.fps),"referenceVideoSeconds":round(times[i]*args.fps)/args.fps,"segment":"A" if times[i]<14 else "B","segmentSeconds":times[i] if times[i]<14 else times[i]-14,"strength":novelty[i]} for i in sorted(peaks)]
    report={"source":str(Path(args.input).resolve()),"source_sha256":sha(args.input),"analysisSeconds":args.seconds,"timingBasis":"local_spectral_flux_heuristic","fixedBPMVerified":False,"fpsReference":args.fps,"candidateOnsets":rows}
    save(out/"candidate-onsets.json",report)
    return {"candidate_onsets":str(out/"candidate-onsets.json"),"count":len(rows),"fixedBPMVerified":False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("prepare");p.add_argument("manifest");p.add_argument("--out",required=True);p.set_defaults(action=prepare)
    p=sub.add_parser("continuity");p.add_argument("--package",required=True);p.add_argument("--a",required=True);p.set_defaults(action=continuity)
    p=sub.add_parser("inspect");p.add_argument("input");p.add_argument("--out",required=True);p.add_argument("--step",type=float,default=.5);p.set_defaults(action=inspect)
    p=sub.add_parser("assemble");p.add_argument("--a",required=True);p.add_argument("--b",required=True);p.add_argument("--music");p.add_argument("--captions");p.add_argument("--style");p.add_argument("--out",required=True);p.add_argument("--work",default="work/duo-mi-post");p.add_argument("--tolerance",type=float,default=.25);p.add_argument("--overwrite",action="store_true");p.set_defaults(action=assemble)
    p=sub.add_parser("music-cues");p.add_argument("input");p.add_argument("--out",required=True);p.add_argument("--seconds",type=float,default=28);p.add_argument("--fps",type=float,default=24);p.set_defaults(action=music_cues)
    args=parser.parse_args()
    try: result=args.action(args)
    except (TaskError,OSError,ValueError,KeyError) as error:
        parser.exit(2,"制作停止："+str(error)+"\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
