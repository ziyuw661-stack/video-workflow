# 团队 AI 自动化视频生产工作流｜独立运行版

固定流程，成员自由选择内容和风格。无需历史 ZIP、中心服务器或统一账号。此版提供真实语音＋图文画面＋字幕＋完整 MP4 的基础生产引擎；更复杂风格由 AI 在本机扩展并实际验证。不是色块测试。

## 直接交给自己的 AI
将仓库链接发给具备本机终端、文件和联网能力的 AI：「读取 AGENTS.md，按我的账号方向自主完成一条正式视频，输出 MP4 和发布包。」AI 负责环境、研究、配置、文稿、分镜、执行及验收，成员仅确认定位、初次风格声线和必要权限。

## 实际命令
先取得私有仓库访问权，安装 Python 3.10+、Git、带 libx264 和 libass 的 FFmpeg（含 ffprobe），并确保在 PATH 中。
```
git clone https://github.com/ziyuw661-stack/video-workflow.git
cd video-workflow
python -m venv .venv
```
Windows: `.venv\Scripts\python.exe`；macOS/Linux: `.venv/bin/python`。以下 python 应使用该环境。
```
python -m pip install -r requirements.txt
python -m pip install yt-dlp
python -m unittest discover -s tests
python produce.py examples/video.json --output output/first-video
```
示例为原创习惯科普完整短片，真实联网语音而非测试音；Edge TTS 需要服务可达，非官方接口且商用条件需确认。如不适用，AI 使用获许可的其他 TTS，逐场景填 audio 和真实 cues 后走同一合成引擎。没有可用真实配音则报告阻塞，不生成假成片。
默认英文字幕 Arial；中文等语言需确认字体支持，必要时配置 style.font（相对路径）、subtitle_font（系统字体名）或 VIDEO_FONT 环境变量。FFmpeg 需要 ass 滤镜。

## 正式生产
AI 复制 templates/profile.json 到 local/profile.json，填写定位并自主调研关键词。
```
python collect.py local/profile.json --output local/trends.csv
```
AI 按 prompts/production.md 查证、原创、准备授权素材、撰写任务 JSON（格式见 examples/video.json），然后：
```
python produce.py local/video.json --output output/my-video
```
每次使用新输出目录。输出 final.mp4（烧录字幕）、final.srt、cover.png、script.json、publish.json、qc.json、场景关键帧。必须观看并试听完整成片，审核事实、素材权利、字幕及美观后方可发布。
画幅和时长由需求决定；基础引擎为图文分镜＋轻动效，支持图片与自定义颜色/字体，并不承诺任意风格。字幕使用真实句级边界，长句拆分时间为估算，须审核。高级动画和真人视频需另行调用实际可用工具。

## 文档
[AI执行规范](AGENTS.md) · [生产流程](WORKFLOW.md) · [质量规则](rules.md) · [生产提示](prompts/production.md) · [状态](STATUS.md)
历史案例在 reference/ 中作为可选参考，不是依赖。demo.py 仅作诊断，非正式生产入口。

当前代码已提交，尚无本机或 CI 成功运行证据，不标记为已验收版本。定时调度及平台发布由 AI 按授权在成员电脑配置，当前不含自动发布程序。
