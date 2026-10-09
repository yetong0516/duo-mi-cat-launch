# 输入与命令

从assets/manifest-template.json复制到任务work目录。相对路径相对于manifest；示例名不是真实猫身份。

字段：cat_name（默认“小猫”）、identity_description（代理读图填写）、photos、music_path（可null）、model（当次模型，默认Seedance 2.0）、cash_budget_rmb（默认0）、quota_note（本次已有授权）、looks（默认五款服饰，可按用户要求配置1–6款）。

照片角色：face_front、body_front、body_left、body_right、body_side（侧别不确定）、body_back、detail；备用portrait、hug、toy。最低应有脸、全身、侧面和背面，不把同一图片复制来冒充视角。优先6张；平台上限更小时先去掉备用/细节。

maximum_identity_images默认6；当次平台限制更小时可降低，给B末帧预留一张。用户明确限定少于4张时可用allow_incomplete_photos=true，但必须记录未覆盖角度并收窄展示，不能假装照片齐全。

prepare生成编号输入图、A/B提示词、角色清单、manifest、字幕草稿和prepared状态。不执行云端生成。

continuity验证A约14秒并提取真实末帧为B的额外参考，更新B提示词及图号；它不是新的身份图。A视觉核验仍需代理完成。

inspect抽取每0.5秒及末帧，保存媒体报告和切镜差分表；差分不证明身份/动作或BPM。

assemble默认每段14秒容差0.25秒，按原片完整时长拼接，不调速；A/B必须同横屏方向和分辨率。省略--captions表示不叠字，省略--music表示静音。音频必要时只转AAC，视频不归一化。字幕版必须重新编码，但透明字形之外没有画面效果。中间文件与编译缓存只写--work。

已有A/B无需照片manifest：复制assets/captions-template.json，替换文字中的${CAT_NAME}及${LOOK_COUNT}（默认“五”），用inspect查看真实镜头后修改时段与留白位置，再传--captions。最后两行end_at_video_end会按实际时长解析。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --out work/cat/package
python3 <skill>/scripts/duo_mi.py continuity --package work/cat/package --a A.mp4
python3 <skill>/scripts/duo_mi.py inspect A.mp4 --out work/cat/qa-a --step 0.5
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --out outputs/cat/final.mp4 --work work/cat/post
python3 <skill>/scripts/duo_mi.py music-cues music.m4a --out work/cat/music --seconds 28
```

music-cues另需NumPy，仅分析用户选定区间的瞬态重音，输出候选重音及24fps参考帧，不声称固定BPM已人工核实。音乐太短时不自动换曲、循环或补造。
