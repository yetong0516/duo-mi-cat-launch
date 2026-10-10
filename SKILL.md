---
name: duo-mi-cat-launch
description: Make a Duo Mi / Apple-style cat launch video from real multi-angle cat photos, generating A14s then B14s with A's last frame, preserving generated backgrounds, and assembling user music plus gradient captions. Also process existing cat-launch A/B clips; add spoken narration only when explicitly requested. Not for standalone pet images or animated desktop pets.
---

# Duo Mi 猫咪发布会：14秒 + 14秒

目标：先真实生成A14秒，再以A末帧接续B14秒，合成约28秒、16:9猫咪发布会视频。默认交付用户指定配乐和渐变配字，不朗读字卡、不加人声旁白。本地代码负责素材、提示词和后期；视频生成由当次可用的外部服务完成。

## 输入

建议**6张同一只猫**：正面脸、正面全身、左侧、右侧、背面、毛色/爪尾细节各1张，覆盖正、左、右、背4个主要视角。最低4张：脸、全身、一个清楚侧面、背面。角度数是制作建议，不是平台上传门槛。可额外收2张拥抱/逗猫棒动作照作备用。

代理读图提取真实脸型、体型、眼鼻及不对称毛色，勿要求用户先写专业描述。未知另一侧不镜像补图，不凭品种编造花纹；缺背面时补图或省略背部镜头。猫名未给可先用“小猫”；音乐未给时可先做静音A/B，不套用其他任务的曲子。真实照片能帮助约束身份，仍需逐段检查生成漂移。

先读 [输入与命令](references/inputs-and-commands.md)，从`assets/manifest-template.json`填本次manifest。不要继承旧猫身份、账号、额度、音乐路径或付款授权。

## 两条入口

- **完整照片生成**：读图→`prepare`→实际A14→下载核验→`continuity`提末帧→实际B14→核验→按真实镜头修订字幕→`assemble`合入指定音乐。读 [生成执行](references/generation.md)。
- **已有A/B**：跳过生成，使用用户指定原片直接拼接。仅要求“拼接加音乐”时不加字或人声；要求静音时保留静音。

单说“配音”“加声音”按音乐或声音后期理解，不自动念字。只有明确要求**旁白或朗读**时才使用下方可选旁白流程。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --out work/cat-launch/package
python3 <skill>/scripts/duo_mi.py inspect A.mp4 --out work/cat-launch/qa-a
python3 <skill>/scripts/duo_mi.py continuity --package work/cat-launch/package --a A.mp4
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --out outputs/cat-launch/final.mp4 --work work/cat-launch/post
```

`<skill>`是当前技能目录。自带后期profile是macOS原生Swift/AVFoundation和Python 3；可选音乐瞬态分析另需NumPy。其他系统需等价的视频工具，不能宣称原生脚本跨平台可运行。默认流程不依赖`say`或中文语音。

## 生成边界

每次检查当前模型、图片限制、14秒、16:9和额度。用户指定优先；模板模型仅是起始选择，须确认当次可用。只上传当前猫身份图，不默认上传含其他猫的设计板。A成功后才给B增加末帧。

准备、参数确认、预计等待、试片都不等于成片。必须下载并解码后再报告取得视频。按当次已授权预算/额度操作，默认不新增现金支出；失败后最多一次有具体修正点且仍在授权额度内的重试，备用模型遵守用户允许范围，不连续盲发或自动购买。

## 原片后期

默认按A→B直接拼接，保留下载原片的背景、构图、动作、速度。不默认抠白底、调色、裁切、缩放、调速或加转场。移除原片生成音轨，换成用户指定音乐；音乐在14秒处不重起。不给默认成片加入机械朗读或其他人声。

配字默认使用最终确认样式，可由用户覆盖：所有字同级，720p为32px，其他分辨率等比；苹方Semibold加粗、横宽90%、字距1.15px；紫蓝至青绿渐变；固定位置，不横移；淡入淡出各0.45秒，片尾也淡出；留出稳定读字时间。造型两句默认**一行同时显示约4秒**。

`assets/captions-template.json`只是草稿。先看真实镜头再调整字幕时段/留白位置，首句不顶格、片尾不遮耳脸，不能为腾字幕位置顺便改画面。读 [配字](references/captions.md)。

## 可选：明确要求旁白或朗读

只有用户明确要求旁白或朗读时，才读 [可选中文旁白](references/narration.md)、用`prepare --prepare-narration`准备稿件，编辑后调用`narrate`。可使用已安装的macOS中文声音、用户录音或已授权语音服务；声音依赖和质量以实际来源为准。默认`prepare`不生成旁白草稿，准备可选稿件也不等于应合成或加入默认成片。

旁白稿与字幕独立；每句必须装入其时窗，超时缩句或调整时窗，不加速画面。含旁白时才按实际讲话窗口压低音乐并输出混合音轨。

## 核验与交付

读 [核验](references/verification.md)。查看脚本生成的关键帧，检查身份、肢体、服装、羽毛、接缝和字幕；默认版核对连续音乐和无额外人声。具备音频理解或试听能力时实际听接缝和片尾；无法试听时保留`listening_qa=pending`，不能把信号检查写成试听通过。交付实际可播放MP4、可编辑字幕和必要偏差；只有明确要求旁白的版本另附旁白稿及讲话时段文件。不用旧片/本地重剪冒充新生成。

14秒文件常有编码尾帧，直接拼接可能约28.08秒；默认保留全部原画面。用户要求精确28.000秒时才明确采用尾帧裁切方案，不悄悄调速。
