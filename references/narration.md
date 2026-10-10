# 可选中文旁白

只有用户明确要求旁白或朗读时才使用本页。照片生成默认使用音乐与字幕，已有A/B按用户指定的音乐和配字处理；所有入口都不自动加入人声或朗读字卡。单说“配音”或“加声音”不触发本流程。历史v0.2.0旁白示范与默认音乐配字成片应分别标明。

## 声音来源

已明确要求旁白时，`narrate`的本地声音缺省参数是macOS `say` / Tingting。先用 `say -v '?'` 检查声音是否可用；`--voice`可指定已安装的中文声音，`--rate`明确调整语速。默认音乐与字幕流程不依赖这些工具。不要把系统声音描述为专业或商业级配音。

用户提供录音或指定已授权的语音服务时优先采用。外部服务的声音、费用、权限和质量以当次可用条件为准；本技能没有内置云端TTS，也不自动开通或购买语音服务。缺少本地中文声音时，使用当次可用的等价工具或明确报告配音依赖。

## 可编辑稿

只有`prepare --prepare-narration`才从`assets/narration-template.json`生成`narration.draft.json`，替换猫名和造型字段，不合成声音。默认`prepare`不生成该稿。

```bash
python3 <skill>/scripts/duo_mi.py prepare manifest.json --prepare-narration --out work/cat/package
```

脚本格式如下；以下是短句示例，可按真实镜头修改：

```json
{
  "durationSeconds": 28,
  "voice": "Tingting",
  "rate": 180,
  "segments": [
    {"start": 4.85, "end": 7.8, "text": "${CAT_NAME}，大有可爱。"},
    {"start": 8.0, "end": 11.3, "text": "可爱，也有质感。"},
    {"start": 15.1, "end": 19.0, "text": "每一面，都有偏爱。"},
    {"start": 24.4, "end": 27.8, "text": "${CAT_NAME}，天生出彩。"}
  ]
}
```

时间单位为秒，均相对于A+B最终时间轴；B的0秒是最终视频约14秒处。占位符为`${CAT_NAME}`、`${LOOK_COUNT}`和`${LOOKS}`；`--manifest`读取本次`cat_name`/`looks`，`--cat-name`和`--looks`可覆盖。不要继承旧猫名。旁白稿和字幕是独立文件，长造型列表通常适合留在字幕或镜头中，避免挤进一句配音。

准备稿保留模板记录，修改台词和时段时只编辑`text`、`start`、`end`。未改写的台词能随新猫名或造型重新替换；已经改成固定文本的相关台词若与覆盖参数冲突，会停止并提示恢复占位符或重新准备草稿，不盲目改写。外部录音不会因为改猫名而重新发声，已记录身份的录音不允许用覆盖参数改成另一只猫。

每句从`start`开始讲话，`end`是允许说完的最晚时间，不要求填满整个时窗。先合成并测量长度，超时会失败并提示缩句、延长时窗或明确选择更快语速；不自动加速视频，也不挪动镜头掩盖超时。相邻语句留出自然停顿，重要动作可留无旁白段。猫名很长时需重新检查时长和发音。

```bash
python3 <skill>/scripts/duo_mi.py narrate --script work/cat/package/narration.draft.json --manifest work/cat/package/manifest.json --out work/cat/narration.m4a --work work/cat/voice
```

输出整段配音和同名`.timing.json`，例如`narration.m4a`与`narration.timing.json`。后者记录测得的实际讲话窗口、文字和长度，用于混音压低音乐；编辑稿保留允许时窗，两者不要混用。

## 使用外部配音

`--external`接受已按最终时间轴排好的**整段**录音，文件从视频0秒对齐，总长不超过稿中的`durationSeconds`。先在语音服务或音频工具中把各句放到正确时间；`narrate`不会自动把一条连续录音拆句并重新定位。

```bash
python3 <skill>/scripts/duo_mi.py narrate --external narration.wav --script timing-and-text.json --out work/cat/narration.m4a --work work/cat/voice
```

`timing-and-text.json`使用相同结构，但`start`/`end`应标实际讲话窗口，供压低配乐使用；核对文字、句间静音和窗口是否匹配录音。外部模式不调用`say`，也不靠字幕时段猜讲话位置。

## 混音与交付

```bash
python3 <skill>/scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --narration work/cat/narration.m4a --narration-timing work/cat/narration.timing.json --out outputs/cat/final.mp4 --work work/cat/post
```

移除生成原片自带声音。音乐从0秒连续播放，14秒处不重启；根据实际讲话窗口压低并恢复配乐，输出一个混合AAC音轨。默认参数为：

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `--music-gain` | `0.8` | 讲话间隙的配乐增益 |
| `--music-duck-gain` | `0.2` | 讲话时的配乐增益 |
| `--narration-gain` | `1.0` | 旁白增益 |
| `--duck-fade` | `0.15` | 压低/恢复音乐的渐变秒数 |

这些混音参数仅对含旁白的版本生效。音量是线性增益，需试听用户实际音乐，避免失真或句尾被盖住。省略`--music`可只保留旁白；省略旁白参数沿用已有纯音乐/静音路径。

查看每句是否说完整、猫名读音是否正确、压低窗口是否覆盖讲话、音乐恢复是否自然，再听14秒接缝和片尾。旁白混音会改变音乐样本，不应套用纯音乐版本的“解码样本完全相同”结论。交付实际MP4、可编辑旁白稿和实际讲话时段文件。
