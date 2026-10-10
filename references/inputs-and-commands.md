# 输入与命令

从assets/manifest-template.json复制到任务work目录。相对路径相对于manifest；示例名不是真实猫身份。

字段：cat_name（默认“小猫”）、identity_description（代理读图填写）、photos、music_path（可null）、model（当次模型，模板起始值须核对服务）、cash_budget_rmb（默认0）、quota_note（本次已有授权）、looks（默认五款服饰，可按用户要求配置1–6款）。

照片角色：face_front、body_front、body_left、body_right、body_side（侧别不确定）、body_back、detail；备用portrait、hug、toy。最低应有脸、全身、侧面和背面，不把同一图片复制来冒充视角。优先6张；平台上限更小时先去掉备用/细节。

maximum_identity_images默认6；当次平台限制更小时可降低，给B末帧预留一张。用户明确限定少于4张时可用allow_incomplete_photos=true，但必须记录未覆盖角度并收窄展示，不能假装照片齐全。

prepare默认生成编号输入图、A/B提示词、角色清单、manifest、captions.draft.json、字幕样式和prepared状态。不准备旁白，不执行云端生成或语音合成。只有明确要求旁白或朗读时才加--prepare-narration，另生成narration.draft.json。

continuity验证A约14秒并提取真实末帧为B的额外参考，更新B提示词及图号；它不是新的身份图。A视觉核验仍需代理完成。

inspect抽取每0.5秒及末帧，保存媒体报告和切镜差分表；差分不证明身份/动作或BPM。

assemble默认每段14秒容差0.25秒，按原片完整时长拼接，不调速；A/B必须同横屏方向和分辨率。默认移除原片生成音轨，合入指定音乐与字幕，不朗读字卡、不加入人声旁白。省略--captions表示不叠字，省略--music则静音。视频不归一化。字幕版必须重新编码，但透明字形之外没有画面效果。中间文件与编译缓存只写--work。

已有A/B无需照片manifest：复制assets/captions-template.json，替换文字中的${CAT_NAME}及${LOOK_COUNT}（默认“五”），用inspect查看真实镜头后修改时段与留白位置，再传--captions。最后两行end_at_video_end会按实际时长解析。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --out work/cat/package
python3 <skill>/scripts/duo_mi.py inspect A.mp4 --out work/cat/qa-a --step 0.5
python3 <skill>/scripts/duo_mi.py continuity --package work/cat/package --a A.mp4
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --out outputs/cat/final.mp4 --work work/cat/post
```

已有A/B只需配乐时省略--captions，不传旁白参数：

```bash
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --out outputs/cat/final.mp4 --work work/cat/post
python3 <skill>/scripts/duo_mi.py music-cues music.m4a --out work/cat/music --seconds 28
```

music-cues另需NumPy，仅分析用户选定区间的瞬态重音，输出候选重音及24fps参考帧，不声称固定BPM已人工核实。音乐太短时不自动换曲、循环或补造。

## 可选：明确要求旁白或朗读

单说“配音”或“加声音”不自动调用narrate。明确要求旁白或朗读时，先用--prepare-narration准备可编辑稿，再按真实镜头改稿。narrate使用macOS say或导入整段外部录音，输出音频及同名.timing.json；每句必须装得进时窗。详见 [可选中文旁白](narration.md)。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --prepare-narration --out work/cat/package
python3 <skill>/scripts/duo_mi.py narrate --script work/cat/package/narration.draft.json --manifest work/cat/package/manifest.json --out work/cat/narration.m4a --work work/cat/voice
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --narration work/cat/narration.m4a --narration-timing work/cat/narration.timing.json --out outputs/cat/with-narration.mp4 --work work/cat/post-narration
```

仅含旁白时才按实际讲话窗口压低音乐并输出混合AAC音轨；省略--music则只保留旁白。此路径不改变默认音乐与字幕成片。
