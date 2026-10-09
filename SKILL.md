---
name: duo-mi-cat-launch
description: Make a Duo Mi / Apple-style cat launch video from real multi-angle cat photos, generating A14s then B14s with A's last frame, preserving generated backgrounds, and assembling music, gradient captions, and timed Chinese narration. Also process existing cat-launch A/B clips while respecting music-only requests. Not for standalone pet images or animated desktop pets.
---

# Duo Mi 猫咪发布会：14秒 + 14秒

目标：先真实生成A14秒，再以A末帧接续B14秒，合成约28秒、16:9猫咪发布会视频。完整照片生成流程默认交付配乐、渐变配字和中文旁白。本地代码负责素材、提示词、配音和后期；视频生成由当次可用的外部服务完成。

## 输入

建议**6张同一只猫**：正面脸、正面全身、左侧、右侧、背面、毛色/爪尾细节各1张，覆盖正、左、右、背4个主要视角。最低4张：脸、全身、一个清楚侧面、背面。角度数是制作建议，不是平台上传门槛。可额外收2张拥抱/逗猫棒动作照作备用。

代理读图提取真实脸型、体型、眼鼻及不对称毛色，勿要求用户先写专业描述。未知另一侧不镜像补图，不凭品种编造花纹；缺背面时补图或省略背部镜头。猫名未给可先用“小猫”；音乐未给时可先做A/B并保留旁白，不套用其他任务的曲子。真实照片能帮助约束身份，仍需逐段检查生成漂移。

先读 [输入与命令](references/inputs-and-commands.md)，从`assets/manifest-template.json`填本次manifest。不要继承旧猫身份、账号、额度、音乐路径或付款授权。

## 两条入口

- **完整照片生成**：读图→`prepare`→实际A14→下载核验→`continuity`提末帧→实际B14→核验→按真实镜头修订字幕和旁白→`narrate`→`assemble`。读 [生成执行](references/generation.md) 和 [中文旁白](references/narration.md)。默认本机macOS `say` / Tingting；有用户指定的配音文件或已授权语音服务时优先采用。
- **已有A/B**：跳过生成，使用用户指定原片直接拼接。仅要求“拼接加音乐”时不加字或配音；要求配音时再走`narrate`和混音。任何入口明确要求无配音、纯音乐或静音，都保留该选择。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --out work/cat-launch/package
python3 <skill>/scripts/duo_mi.py inspect A.mp4 --out work/cat-launch/qa-a
python3 <skill>/scripts/duo_mi.py continuity --package work/cat-launch/package --a A.mp4
python3 <skill>/scripts/duo_mi.py narrate --script work/cat-launch/package/narration.draft.json --manifest work/cat-launch/package/manifest.json --out work/cat-launch/narration.m4a --work work/cat-launch/voice
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --narration work/cat-launch/narration.m4a --narration-timing work/cat-launch/narration.timing.json --out outputs/cat-launch/final.mp4 --work work/cat-launch/post
```

`<skill>`是当前技能目录。自带后期与本地配音profile是macOS原生Swift/AVFoundation、`say`和Python 3；可选音乐瞬态分析另需NumPy。先检查中文声音是否可用。其他系统需等价的视频和语音工具，不能宣称原生脚本跨平台可运行。自然语音的质量依赖实际声音或外部服务，本机基线不承诺商业配音水准。

## 生成边界

每次检查当前模型、图片限制、14秒、16:9和额度。用户指定优先；模板模型仅是起始选择，须确认当次可用。只上传当前猫身份图，不默认上传含其他猫的设计板。A成功后才给B增加末帧。

准备、参数确认、预计等待、试片都不等于成片。必须下载并解码后再报告取得视频。按当次已授权预算/额度操作，默认不新增现金支出；失败后最多一次有具体修正点且仍在授权额度内的重试，备用模型遵守用户允许范围，不连续盲发或自动购买。

## 原片后期

默认按A→B直接拼接，保留下载原片的背景、构图、动作、速度。不默认抠白底、调色、裁切、缩放、调速或加转场。移除原片生成音轨，完整照片流程加入中文旁白与用户指定音乐；音乐在14秒处不重起。已有纯音乐流程保持原有做法。

旁白稿与字幕独立：句子可更短，给微距、编舞和动作留呼吸。每句录音必须装入其编辑时窗；超时缩句或调整旁白时窗，不加速画面。使用生成的实际讲话时段压低音乐，输出一个混合AAC音轨。详情见 [中文旁白](references/narration.md)。

配字默认使用最终确认样式，可由用户覆盖：所有字同级，720p为32px，其他分辨率等比；苹方Semibold加粗、横宽90%、字距1.15px；紫蓝至青绿渐变；固定位置，不横移；淡入淡出各0.45秒，片尾也淡出；留出稳定读字时间。造型两句默认**一行同时显示约4秒**。

`assets/captions-template.json`只是草稿。先看真实镜头再调整字幕时段/留白位置，首句不顶格、片尾不遮耳脸，不能为腾字幕位置顺便改画面。读 [配字](references/captions.md)。

## 核验与交付

读 [核验](references/verification.md)。查看脚本生成的关键帧，检查身份、肢体、服装、羽毛、接缝和字幕；具备音频理解或试听能力时，实际听配音、接缝和音乐恢复。无法试听时保留`listening_qa=pending`，交付可播放预览并说明尚未主观核验，不能把音轨信号检查写成试听通过。交付实际可播放MP4、可编辑字幕/旁白稿和必要偏差，不用旧片/本地重剪冒充新生成。

14秒文件常有编码尾帧，直接拼接可能约28.08秒；默认保留全部原画面。用户要求精确28.000秒时才明确采用尾帧裁切方案，不悄悄调速。
