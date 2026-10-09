#!/usr/bin/env python3
"""Prepare cat-launch generation inputs and run conservative local post-production."""
import argparse
import array
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
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

def bounded(value, name, minimum=0, maximum=3600):
    if isinstance(value,bool): raise TaskError(name+"须为有限数值。")
    result=float(value)
    if not math.isfinite(result) or not minimum<=result<=maximum:
        raise TaskError(f"{name}须为{minimum}–{maximum}之间的有限数值。")
    return result

def narration_variables(name, looks):
    if not isinstance(looks,list) or not 1<=len(looks)<=6 or not all(isinstance(x,str) and x.strip() for x in looks):
        raise TaskError("looks需为1–6个非空造型名称。")
    name=str(name).strip()
    if not name or len(name)>24 or "\n" in name: raise TaskError("猫名须为1–24字的单行文本。")
    return {"CAT_NAME":name,"LOOK_COUNT":"一二三四五六"[len(looks)-1],"LOOKS":"、".join(looks)}

def template_keys(text):
    return {match.group("named") or match.group("braced") for match in Template.pattern.finditer(text) if match.group("named") or match.group("braced")}

def resolve_narration(script, variables, override_keys=None):
    if not isinstance(script,dict) or not isinstance(script.get("segments"),list) or not all(isinstance(item,dict) for item in script["segments"]):
        raise TaskError("旁白JSON须为对象，segments须为分段对象数组。")
    data=dict(script);data["segments"]=[dict(item) for item in script.get("segments",[])]
    previous=script.get("templateVariables")
    if previous is not None and not isinstance(previous,dict): raise TaskError("templateVariables须为对象；请保留prepare生成的模板记录。")
    keys=set().union(*(template_keys(str(item.get("text",""))) for item in data["segments"]))
    if override_keys and previous is None and (("CAT_NAME" in override_keys and "CAT_NAME" not in keys) or (override_keys & {"LOOK_COUNT","LOOKS"} and not keys & {"LOOK_COUNT","LOOKS"})):
        raise TaskError("这份旁白缺少对应变量的模板记录，无法安全应用猫名/造型覆盖。请重新prepare生成草稿，或在需要变化的台词中恢复${CAT_NAME}/${LOOK_COUNT}/${LOOKS}；不要盲目替换已编辑台词。")
    changed={key for key,value in variables.items() if previous is not None and previous.get(key)!=value}
    for index,item in enumerate(data["segments"],1):
        text=str(item.get("text",""))
        original=item.get("templateText")
        # Rebind untouched generated text; user-edited text is authoritative.
        source=original if isinstance(original,str) and text==item.get("resolvedText") else text
        dependencies=set(item.get("templateKeys",[])) | template_keys(original or "") | template_keys(source)
        missing=(changed & dependencies)-template_keys(source)
        if missing:
            tokens="/".join("${"+key+"}" for key in sorted(missing))
            raise TaskError(f"旁白{index}已编辑为固定文本，无法安全应用覆盖变量{tokens}。请在该句text中恢复占位符，或移除冲突的猫名/造型覆盖；脚本保留原台词，不会盲目替换。")
        item["templateText"]=source
        item["templateKeys"]=sorted(dependencies)
        item["text"]=Template(source).substitute(variables).strip()
        item["resolvedText"]=item["text"]
    data["templateVariables"]=variables
    return data

def speech_windows(rows, duration, require_text=False):
    if not isinstance(rows,list) or not 1<=len(rows)<=64: raise TaskError("旁白需有1–64个segments。")
    result=[];previous=0
    for index,row in enumerate(rows,1):
        if not isinstance(row,dict): raise TaskError(f"旁白{index}须为包含start/end的对象。")
        start=bounded(row["start"],f"旁白{index} start",0,duration)
        end=bounded(row["end"],f"旁白{index} end",0,duration)
        if end<=start or start<previous-1e-6: raise TaskError(f"旁白{index}的时间窗须有正时长，按时间排序且不能重叠。")
        text=str(row.get("text", "")).strip()
        if require_text and (not text or len(text)>500): raise TaskError(f"旁白{index}须填写1–500字的可编辑文本。")
        result.append(dict(row,start=start,end=end,text=text));previous=end
    return result

def protect(destination, sources):
    if Path(destination).resolve() in {Path(source).resolve() for source in sources if source}:
        raise TaskError("不能覆盖源文件: "+str(destination))

def silence(path, duration):
    with wave.open(str(path),"wb") as stream:
        stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(44100)
        remaining=round(duration*44100)
        while remaining:
            count=min(remaining,44100);stream.writeframes(b"\0"*(count*4));remaining-=count

def narrate(args):
    script_path=Path(args.script).resolve();script=read(script_path)
    manifest=read(args.manifest) if args.manifest else {}
    if not isinstance(script,dict): raise TaskError("旁白JSON须为对象。")
    looks=args.looks or manifest.get("looks") or script.get("looks") or read(SKILL/"assets/manifest-template.json")["looks"]
    variables=narration_variables(args.cat_name or manifest.get("cat_name") or script.get("cat_name") or "小猫",looks)
    if args.external and isinstance(script.get("templateVariables"),dict) and any(script["templateVariables"].get(key)!=value for key,value in variables.items()):
        raise TaskError("外部录音不能通过猫名/造型参数改写已讲出的内容。请提供与新猫名/造型匹配的录音及时间报告，或保留该录音原有的变量。")
    overrides={"CAT_NAME"} if args.cat_name or manifest.get("cat_name") else set()
    if args.looks or manifest.get("looks"): overrides.update({"LOOK_COUNT","LOOKS"})
    script=resolve_narration(script,variables,overrides if not args.external else None)
    duration=bounded(args.duration if args.duration is not None else script.get("durationSeconds",28),"旁白总时长",.1,3600)
    rows=speech_windows(script.get("segments"),duration,require_text=not args.external)
    output=Path(args.out).resolve();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
    if output.suffix.lower()!=".m4a": raise TaskError("旁白输出请使用.m4a扩展名（AAC）。")
    sidecar=output.with_suffix(".timing.json")
    if (output.exists() or sidecar.exists()) and not args.overwrite: raise TaskError("旁白输出或时间报告已存在；选新文件名或明确--overwrite。")
    external=Path(args.external).resolve() if args.external else None
    sources=[script_path,args.manifest,external]
    for destination in [output,sidecar,work/"silence.wav",work/"narration-mix.json",work/"narration-mix-report.json",work/"narration-media.json",work/"external-media.json"]: protect(destination,sources)
    inputs=[];measured=[];voice=None;rate=None
    if external:
        metadata=probe(external,work/"external-media.json",work)
        if metadata.get("audioTracks")!=1: raise TaskError("外部旁白须有一个音频轨。")
        length=bounded(metadata["audioDurationSeconds"],"外部旁白时长",.01,3600)
        if length>duration+.001: raise TaskError(f"外部旁白长{length:.3f}s，超过{duration:.3f}s时间线；请先剪辑旁白或调整台词，不能改视频速度。")
        if rows[-1]["end"]>length+.02: raise TaskError("外部旁白的最后讲话时间窗超出音频时长；请修正segments。")
        inputs.append({"file":str(external),"start":0,"duration":length,"gain":1})
        measured=[dict(row,speechDurationSeconds=row["end"]-row["start"]) for row in rows]
    else:
        if sys.platform!="darwin" or not shutil.which("say"): raise TaskError("本地旁白生成需要macOS say；其他平台可使用--external提供已录制旁白。")
        voice=args.voice or script.get("voice","Tingting")
        available=command(["say","-v","?"])
        if not isinstance(voice,str) or not re.search(r"^"+re.escape(voice)+r"\s",available,re.MULTILINE): raise TaskError("本机未安装所选say声音；运行 say -v '?' 查看，然后用--voice选择。")
        rate=int(bounded(args.rate if args.rate is not None else script.get("rate",180),"旁白语速",80,400))
        for index,row in enumerate(rows,1):
            textfile=work/f"speech-{index:02d}.txt";audio=work/f"speech-{index:02d}.aiff";metadata=work/f"speech-{index:02d}.json"
            for destination in [textfile,audio,metadata]: protect(destination,sources)
            textfile.write_text(row["text"],encoding="utf-8")
            command(["say","-v",voice,"-r",rate,"-f",textfile,"-o",audio])
            info=probe(audio,metadata,work);length=bounded(info["audioDurationSeconds"],f"旁白{index}时长",.01,3600)
            budget=row["end"]-row["start"]
            if length>budget+.001: raise TaskError(f"旁白{index}「{row['text']}」实测{length:.3f}s，时间窗仅{budget:.3f}s，超出{length-budget:.3f}s。请缩短台词、调整该时间窗，或明确选择--rate；脚本不会加速视频。分段音频保留在{audio}。")
            inputs.append({"file":str(audio),"start":row["start"],"duration":length,"gain":1})
            measured.append(dict(row,plannedEnd=row["end"],end=row["start"]+length,speechDurationSeconds=length,source=str(audio),source_sha256=sha(audio)))
    silent=work/"silence.wav";silence(silent,duration)
    config={"durationSeconds":duration,"music":None,"musicGain":1,"musicDuckGain":1,"duckFadeSeconds":0,"windows":[],"inputs":[{"file":str(silent),"start":0,"duration":duration,"gain":1},*inputs]}
    save(work/"narration-mix.json",config);native("mix_audio",[work/"narration-mix.json",output,work/"narration-mix-report.json"],work)
    final=probe(output,work/"narration-media.json",work)
    if final.get("audioTracks")!=1 or abs(final["audioDurationSeconds"]-duration)>.025: raise TaskError("旁白导出时长或音轨数量不符合时间线。")
    report={"file":str(output),"file_sha256":sha(output),"durationSeconds":duration,"audioDurationSeconds":final["audioDurationSeconds"],"audioTracks":1,"voice":voice,"rate":rate,"method":"external_recording" if external else "macOS_say","externalSource":str(external) if external else None,"externalSource_sha256":sha(external) if external else None,"cat_name":variables["CAT_NAME"],"looks":looks,"templateVariables":script["templateVariables"],"segments":measured,"speechWindowBasis":"user_supplied_windows" if external else "measured_synthesized_segment_duration_including_pauses","quietSpacesIncluded":True,"technical_qa":"passed","listening_qa":"pending"}
    save(sidecar,report)
    return {"narration":str(output),"timing":str(sidecar),"durationSeconds":duration,"segments":len(measured),"technical_qa":"passed","listening_qa":"pending"}

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
    narration=resolve_narration(read(SKILL/"assets/narration-template.json"),narration_variables(name,looks))
    narration.update(cat_name=name,looks=looks)
    save(package/"narration.draft.json",narration)
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

def audio_check(reference,final,work,label="音乐"):
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
    if score<.995: raise TaskError(f"{label}信号不匹配，相关性{score:.4f}；请检查音频封装。")
    return {"exactDecodedSamples":False,"sampleRate":44100,"signalCorrelation":score,"measuredInterleavedSampleOffset":lag,"timeOffsetSeconds":lag/(44100*2)}

def assemble(args):
    output=Path(args.out).resolve();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() and not args.overwrite: raise TaskError("输出已存在；选新文件名或明确--overwrite。")
    a,b=Path(args.a).resolve(),Path(args.b).resolve()
    if output in {a,b}: raise TaskError("不能覆盖源片段。")
    if bool(args.narration)!=bool(args.narration_timing): raise TaskError("--narration与--narration-timing须一起提供；旁白时间窗用于配乐避让和核验。")
    sources=[a,b,args.music,args.narration,args.narration_timing,args.captions,args.style]
    for destination in [output,output.with_suffix(".verification.json"),*[work/name for name in ["A-media.json","B-media.json","music-media.json","music-aac.m4a","original-assembly.mp4","video-passthrough.json","concat.json","captions.resolved.json","captioned-silent.mp4","captions-report.json","mux.json","final-media.json","music-reference.raw","music-export.raw","narration-media.json","mix-silence.wav","mix.json","mixed-audio.m4a","mix-report.json"]]]:
        protect(destination,sources)
    tolerance=bounded(args.tolerance,"tolerance",0,1)
    pa=probe(a,work/"A-media.json",work);pb=probe(b,work/"B-media.json",work)
    video_ok(pa,tolerance);video_ok(pb,tolerance)
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
    narration=None;timing=None;mix_report=None;final_audio=music
    if args.narration:
        narration=Path(args.narration).resolve();timing=read(args.narration_timing)
        declared=bounded(timing["durationSeconds"],"旁白报告总时长",.1,3600)
        if declared>expected+.001: raise TaskError(f"旁白时间线长{declared:.3f}s，超过源视频{expected:.3f}s；请修正旁白，不能加速或裁切视频。")
        windows=speech_windows(timing.get("segments"),declared)
        if timing.get("file_sha256") and timing["file_sha256"]!=sha(narration): raise TaskError("旁白文件与时间报告的SHA256不匹配；请重新生成报告或选正确音频。")
        np=probe(narration,work/"narration-media.json",work)
        if np.get("audioTracks")!=1: raise TaskError("旁白须为一个音频轨。")
        nd=bounded(np["audioDurationSeconds"],"旁白实测时长",.01,3600)
        if nd>expected+.025 or abs(nd-declared)>.025: raise TaskError("旁白文件时长与报告/视频不符；请先对齐完整时间线。")
        music_gain=bounded(args.music_gain,"music-gain",0,1)
        duck_gain=bounded(args.music_duck_gain,"music-duck-gain",0,music_gain)
        voice_gain=bounded(args.narration_gain,"narration-gain",0,1)
        fade=bounded(args.duck_fade,"duck-fade",0,2)
        silent=work/"mix-silence.wav";silence(silent,expected)
        config={"durationSeconds":expected,"music":str(music) if music else None,"musicGain":music_gain,"musicDuckGain":duck_gain,"duckFadeSeconds":fade,"windows":[{"start":row["start"],"end":row["end"]} for row in windows],"inputs":[{"file":str(silent),"start":0,"duration":expected,"gain":1},{"file":str(narration),"start":0,"duration":nd,"gain":voice_gain}]}
        save(work/"mix.json",config);final_audio=work/"mixed-audio.m4a"
        native("mix_audio",[work/"mix.json",final_audio,work/"mix-report.json"],work);mix_report=read(work/"mix-report.json")
        if mix_report["audioTracks"]!=1 or abs(mix_report["durationSeconds"]-expected)>.025: raise TaskError("混音时长或音轨数量不符合视频时间线。")
    raw=work/"original-assembly.mp4"
    native("concat",[a,b,final_audio or "-",raw,work/"concat.json",*(["mixed"] if narration else [])],work)
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
        if final_audio: native("mux",[titled,final_audio,output,work/"mux.json",*(["mixed"] if narration else [])],work)
        else: shutil.copy2(titled,output)
    else: shutil.copy2(raw,output)
    final=probe(output,work/"final-media.json",work,work/"final-qa",2)
    if abs(final["videoDurationSeconds"]-expected)>.02 or final["frames"]!=pa["frames"]+pb["frames"]:
        raise TaskError("后期改变了源视频时长或帧数，请检查导出。")
    if final["audioTracks"]!=(1 if final_audio else 0): raise TaskError("最终音轨数量不正确。")
    verification=audio_check(original_music,output,work) if music and not narration else None
    mixed_verification=audio_check(final_audio,output,work,"混音") if narration else None
    if mixed_verification:
        samples=pcm(work/"music-export.raw")
        mixed_verification.update(reference="mixed_audio_export",reference_sha256=sha(final_audio),peakDecodedPCM16=max(abs(x) for x in samples),samplesAtFullScale=sum(x in {-32768,32767} for x in samples))
    report={"final":str(output),"durationSeconds":final["durationSeconds"],"resolution":[final["width"],final["height"]],"frames":final["frames"],"audioTracks":final["audioTracks"],"sources":[{"file":str(p),"sha256":sha(p)} for p in [a,b]],"musicSource":str(original_music) if music else None,"musicSource_sha256":sha(original_music) if music else None,"musicConvertedToAAC":music_converted,"musicVerification":verification,"narrationSource":str(narration) if narration else None,"narrationSource_sha256":sha(narration) if narration else None,"narrationTiming":timing,"mixReport":mix_report,"mixedAudioVerification":mixed_verification,"captionsApplied":bool(args.captions),"captionReport":title_report,"backgroundReplaced":False,"speedChanged":False,"cropOrResizeApplied":False,"voiceoverAdded":bool(narration),"generation_performed_by_script":False,"technical_qa":"passed","visual_qa":"pending","listening_qa":"pending" if narration else None,"final_sha256":sha(output)}
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
    p=sub.add_parser("narrate");p.add_argument("--script",required=True);p.add_argument("--manifest");p.add_argument("--cat-name");p.add_argument("--looks",nargs="+");p.add_argument("--voice");p.add_argument("--rate",type=float);p.add_argument("--duration",type=float);p.add_argument("--external");p.add_argument("--out",required=True);p.add_argument("--work",default="work/duo-mi-narration");p.add_argument("--overwrite",action="store_true");p.set_defaults(action=narrate)
    p=sub.add_parser("assemble");p.add_argument("--a",required=True);p.add_argument("--b",required=True);p.add_argument("--music");p.add_argument("--narration");p.add_argument("--narration-timing");p.add_argument("--music-gain",type=float,default=.8);p.add_argument("--music-duck-gain",type=float,default=.2);p.add_argument("--narration-gain",type=float,default=1);p.add_argument("--duck-fade",type=float,default=.15);p.add_argument("--captions");p.add_argument("--style");p.add_argument("--out",required=True);p.add_argument("--work",default="work/duo-mi-post");p.add_argument("--tolerance",type=float,default=.25);p.add_argument("--overwrite",action="store_true");p.set_defaults(action=assemble)
    p=sub.add_parser("music-cues");p.add_argument("input");p.add_argument("--out",required=True);p.add_argument("--seconds",type=float,default=28);p.add_argument("--fps",type=float,default=24);p.set_defaults(action=music_cues)
    args=parser.parse_args()
    try: result=args.action(args)
    except (TaskError,OSError,ValueError,KeyError) as error:
        parser.exit(2,"制作停止："+str(error)+"\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
