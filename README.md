# Duo Mi 猫咪发布会 Skill

用真实、多角度猫咪照片制作 Duo Mi / Apple 风格的猫咪发布会视频：**A段14秒 → A末帧衔接B段14秒 → 原片拼接＋指定配乐＋渐变配字**。

## 准备什么

推荐6张同一只猫的照片：正面脸、正面全身、左侧全身、右侧全身、背面、毛色/爪尾细节各1张。4张也可开始：脸、全身、一个清楚侧面、背面。另提供猫名和希望使用的音乐。

没有另一侧写真时，只展示已知侧面，不把图片镜像来伪造毛色。生成需要可用的视频生成服务；自带脚本不包含生成模型，也不自动购买或充值。

## 主要能力

- 参数化身份照片、猫名、模型与造型；默认五款，也可配置1–6款。
- 分开生成前14秒与后14秒，B附A真实末帧，避免把预计等待或试片当成成片。
- 后期默认保留原片背景、构图、动作及速度，只拼接、叠字和加入指定音乐。
- 统一小号加粗字、细长比例、紫蓝至青绿渐变、0.45秒淡入/淡出。
- “五种造型，一样可爱。 每一面，都有偏爱。”默认合并为一行，同时显示约4秒。
- 媒体、帧数、音轨和音乐信号核验；字幕留白仍需实际查看画面。

## 使用

把本仓库放入支持SKILL.md的代理技能目录。在Codex中可放入 `~/.codex/skills/duo-mi-cat-launch`，然后调用：

```text
使用 $duo-mi-cat-launch，用这几张猫咪照片和这份音乐，制作前14秒＋后14秒发布会视频。
```

完整执行说明见 [SKILL.md](SKILL.md)。输入结构与命令见 [references/inputs-and-commands.md](references/inputs-and-commands.md)。

自带后期执行profile为 **macOS + Python 3 + Swift/AVFoundation**；核心Python命令仅用标准库。可选音乐重音分析另需NumPy。其他操作系统需提供等价的视频工具和生成服务连接。

```bash
python3 scripts/duo_mi.py prepare manifest.json --out work/cat/package
python3 scripts/duo_mi.py continuity --package work/cat/package --a A.mp4
python3 scripts/duo_mi.py inspect A.mp4 --out work/cat/qa-a
python3 scripts/duo_mi.py assemble --a A.mp4 --b B.mp4 --music music.m4a --captions captions.json --out outputs/cat/final.mp4 --work work/cat/post
```

## 目录

- `assets/`：输入、分镜提示词、统一文字样式与字幕草稿。
- `scripts/`：照片准备、末帧提取、原片拼接、字幕渲染和音轨核验。
- `references/`：生成、配字与核验规则。
- `agents/`：Codex技能界面配置。
- `tools/package_skillhub.py`：生成腾讯SkillHub适配包，不修改Codex原版。

## 验证范围

已使用现成A/B原片完成本地前向测试：新猫名替换、28.08秒、1280×720、674帧、单音轨、指定音乐解码样本一致、原片背景保留。WAV转AAC分支、重复图片拒绝、1/3/5款参数化也已验证。

云端新生成效果和额度以每次实际服务结果为准。编码尾帧可使原样拼接略超过28秒；默认保留完整画面。素材图片、音乐、账号信息及本地测试日志均不在仓库中。
