# Duo Mi 猫咪发布会 Skill

提供自己猫咪的多角度照片，让支持技能的代理制作一支约28秒、16:9的 Duo Mi / Apple 风格发布会视频：**A段14秒 → A真实末帧接续B段14秒 → 原片拼接＋指定音乐＋渐变配字**。

v0.2.1 的默认成片使用音乐和字幕，不加入朗读或人声旁白。v0.2.0引入的定时旁白、本地语音和外部录音功能仍然保留，只有明确要求“旁白”或“朗读”时才使用。单说“配音”或“加声音”按音乐或声音后期处理，不自动念字。

公开代码与技能：[GitHub 仓库](https://github.com/yetong0516/duo-mi-cat-launch)。

## PONY 成片

https://github.com/user-attachments/assets/ebb80d1b-20eb-403c-b901-aba5be528239

[下载原画质完整MP4](https://github.com/yetong0516/duo-mi-cat-launch/releases/download/v0.2.1/PONY_duo_mi_final_music.mp4) · [视频与技能下载页](https://github.com/yetong0516/duo-mi-cat-launch/releases/tag/v0.2.1)

约28秒，保留原片背景、构图、动作和速度，包含背景音乐与渐变字卡，没有人声旁白。播放器使用压缩展示版，下载链接提供原画质成片。

## 准备素材与环境

- 推荐6张同一只猫的清晰照片：正面脸、正面全身、左侧全身、右侧全身、背面、毛色/爪尾细节各1张。最低4张：脸、全身、一个清楚侧面、背面。
- 提供猫名和希望使用的音乐；可以再提供喜欢的造型。代理会从照片识别真实外貌，无需先写专业毛色描述。
- 需要一个当前可用、支持参考图和所需时长的视频生成服务。脚本不含视频模型，也不自带额度或自动购买、充值。
- 自带后期需要 **macOS + Python 3 + Swift/AVFoundation**。其他系统需要等价的视频工具；可选音乐重音分析另需NumPy。默认音乐与字幕流程不需要`say`或中文语音。

照片帮助约束身份，但不能保证所有猫、所有镜头都完美还原或接缝无痕。没有另一侧照片时，只展示已知侧面，不镜像伪造毛色。模型、额度和生成质量以每次实际服务结果为准。

## 安装与调用

把仓库放入支持 `SKILL.md` 的代理技能目录。在Codex中可以安装到 `~/.codex/skills/duo-mi-cat-launch`：

```bash
git clone https://github.com/yetong0516/duo-mi-cat-launch.git ~/.codex/skills/duo-mi-cat-launch
```

已有同名安装时更新该目录。附上猫咪照片和音乐后，复制这段调用并替换猫名即可：

```text
使用 $duo-mi-cat-launch，为我提供的同一只猫的多角度照片制作 Duo Mi 猫咪发布会视频。
猫名：团团。配乐：我上传的音乐文件。
先生成 A 段14秒，再用 A 的真实末帧接续生成 B 段14秒。
保留生成原片的背景、构图、动作和速度，加入我提供的音乐和渐变配字。
交付实际可播放的最终 MP4，并检查猫咪身份、接缝、配字和音乐。
```

如果已有满意的A/B原片，可以直接说“使用 $duo-mi-cat-launch，把这两段原片拼接并加入这份音乐，不加字”。

## 从照片到音乐与字幕成片

以下命令供执行代理或需要手动操作的读者使用，工作目录为本仓库。相对素材路径以 `manifest.json` 所在目录为基准。

1. 复制 [输入模板](assets/manifest-template.json) 到任务目录，填写猫名、照片路径、音乐、当次模型和造型；代理读图填写 `identity_description`。详见 [输入与命令](references/inputs-and-commands.md)。

   ```bash
   python3 scripts/duo_mi.py prepare manifest.json --out work/cat/package
   ```

   这会准备参考图、A/B提示词、字幕草稿与样式，尚未生成视频，不准备旁白或调用语音合成。

2. 用已连接的视频服务，上传准备包中的身份图和A提示词，实际生成并下载A。查看视频和关键帧，确认身份、动作及媒体参数后再继续。详见 [生成执行](references/generation.md)。

   ```bash
   python3 scripts/duo_mi.py inspect A.mp4 --out work/cat/qa-a
   python3 scripts/duo_mi.py continuity --package work/cat/package --a A.mp4
   ```

3. 把A的真实末帧与身份图一起提交给服务，使用更新后的B提示词，生成并下载B。检查实际接缝与造型。

   ```bash
   python3 scripts/duo_mi.py inspect B.mp4 --out work/cat/qa-b
   ```

4. 根据真实镜头修订准备包中的 `captions.draft.json`，选择不遮挡猫脸、耳朵和动作的留白，再拼接原片并加入字幕与指定音乐。

   ```bash
   python3 scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions work/cat/package/captions.draft.json --out outputs/cat/final.mp4 --work work/cat/post
   ```

   原片生成音轨会移除，音乐连续通过14秒接缝，不从头重放。默认命令不合成语音，也不朗读字幕；省略`--music`可制作静音版，省略`--captions`则不叠字。

5. 查看最终MP4，检查猫咪身份、肢体、造型、接缝和字幕遮挡；核对音乐连续、没有额外人声。交付成片及可编辑字幕，详见 [核验](references/verification.md)。

## 可选：明确要求旁白或朗读

只有你明确说要旁白或朗读，才增加这一部分。此时在照片准备步骤加上`--prepare-narration`，生成可编辑的`narration.draft.json`；该参数只准备稿件，不生成声音。可用macOS `say`与已安装的中文声音，也可提供自己录制或语音服务生成的整段录音。按真实镜头改稿，再合成并检查每句是否装得进时窗；超时缩句或调整时窗，不加速画面。声音的自然度取决于实际声音或录音，本机基线不承诺商业配音水准。

```bash
python3 scripts/duo_mi.py prepare manifest.json --prepare-narration --out work/cat/package
python3 scripts/duo_mi.py narrate --script work/cat/package/narration.draft.json --manifest work/cat/package/manifest.json --out work/cat/narration.m4a --work work/cat/voice
python3 scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions work/cat/package/captions.draft.json --narration work/cat/narration.m4a --narration-timing work/cat/narration.timing.json --out outputs/cat/with-narration.mp4 --work work/cat/post-narration
```

含旁白时才按实际讲话时段压低配乐。外部录音需从最终视频0秒对齐，并在稿中标出实际讲话窗口；不会自动拆句定位。完整格式、声音检查和混音参数见 [可选中文旁白](references/narration.md)。

## 画面与配字

后期保留下载原片的背景、构图、动作及速度，不默认裁切、抠白底、调色、缩放、调速或加转场。字幕采用统一小号加粗字、细长比例、紫蓝至青绿渐变、0.45秒淡入/淡出；所有字固定位置，按真实画面选择留白。

“五种造型，一样可爱。 每一面，都有偏爱。”默认合并为一行，同时显示约4秒。造型可配置1–6款，文案随数量替换。字幕样式可按本次要求修改，见 [配字](references/captions.md)。

两段编码尾帧可能让完整拼接略超过28秒，默认保留全部原画面；需要精确28.000秒时明确处理尾帧，不悄悄调速。

## 文件与验证范围

- `SKILL.md`：代理入口、两条制作路径与交付要求。
- `assets/`：照片输入、分镜、字幕样式、字幕与可选旁白模板。
- `scripts/`：准备、末帧提取、配音、拼接、配字和音轨核验。
- `references/`：生成、命令、旁白、配字与核验规则。
- `agents/`：Codex技能界面配置。
- `tools/package_skillhub.py`：生成腾讯SkillHub适配包。

PONY默认展示的是音乐与配字版本，没有人声旁白。v0.2.0另存的旁白示范用于验证可选声音后期，不代表重新从照片生成视频，也不改变默认制作选择。已有原片验证包括帧数/时间轴、指定音乐、背景保留及参数化造型；新生成仍须每次实际检查服务结果。仓库仅展示成片预览，猫咪身份照片原件、独立音乐文件、账号信息及本地测试日志不在技能包中。
