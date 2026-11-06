# 方圆萌宠表情包 Skill

上传宠物照片，让支持 Skill 的 AI 工具完成：确认形象 → 透明素材 → 稳定中文配字 → 轻动效 GIF → 微信素材检查与打包。

默认真实萌宠风，保留宠物的耳型、毛色与体态；可按要求换画风。源自珍珠表情包实际制作过程。当前脚本使用单姿势加轻动效，完整肢体动作需要额外连续帧或视频工具。

## 安装与使用

以 Codex 为例，将本仓库放到 `~/.codex/skills/fangyuan-pet-stickers`。也可从 GitHub 的 **Code → Download ZIP** 下载，解压后放入宿主的 skills 目录，文件夹命名为 `fangyuan-pet-stickers`。

```bash
git clone https://github.com/klaybloom/fangyuan-pet-stickers.git ~/.codex/skills/fangyuan-pet-stickers
```

上传照片，然后说：

> 用 fangyuan-pet-stickers，把这只宠物做成 16 张真实萌宠风微信表情。先给我看一张小样，确认后继续做整套，保留中文文案，最后给我 GIF 和完整素材 ZIP。

需要宿主具备图片生成/编辑和本地脚本执行能力。普通聊天窗口未必能安装或运行 Skill，请按当前工具的能力使用。Python 3.10+、Pillow 和本地中文字体用于导出。Skill 不提供模型额度，不保证零成本。

## 产物

- 512×512 高清 GIF 与 240×240 微信尺寸 GIF
- 120×120 缩略图、240×240 封面、50×50 图标、750×400 横幅
- 可选赞赏两图（需要另行生成后提供）
- 浅底/深底动态预览、静态总览、投稿文案、技术校验报告、完整 ZIP

示例配置见 [manifest.example.json](references/manifest.example.json)，命令入口为 [scripts/stickers.py](scripts/stickers.py)。脚本不生图、不抠复杂背景、不联网、不自动投稿。

默认 16 张，可在当前制作基线的 8–24 张之间设置。具体规格与验收边界见 [references/wechat.md](references/wechat.md)。

## 复用与验证

本项目独立实现打包脚本，方法参考了实际珍珠制作记录；参考项目 [pixel-gif-sticker-pack](https://github.com/WoYun520/pixel-gif-sticker-pack) 提供了图集与轻动效的思路。本仓库未复制其代码或打包用户原始照片。

MIT License。微信审核和上架需要单独操作，工具不保证审核结果。
