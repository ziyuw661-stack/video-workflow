# 团队 AI 自动化视频生产工作流

会议演示预览｜固定流程、灵活风格、个人独立运行。

## 立即演示
要求 Python 3 和 PATH 中的 FFmpeg、ffprobe。Windows 可使用 py 替代 python。Mac/Linux 可使用 python3。以下命令须在仓库目录运行：

```bash
git clone https://github.com/ziyuw661-stack/video-workflow.git
cd video-workflow
python demo.py
python demo.py --vertical --output demo-vertical
```

私有仓库需本人 GitHub 登录及访问权限。FFmpeg 官方下载：https://ffmpeg.org/download.html

输出 demo-output/demo.mp4、demo.srt、report.json。演示仅为四秒合成冒烟测试，画面为色块、声音为测试音调，字幕为软字幕，不是正式 AI 成片。当前仓库演示脚本尚未实机验证；命令失败时检查依赖并报告真实错误。

## 如何交给 AI
将仓库链接交给有本地终端及文件操作能力的 AI，发送：「读取 AGENTS.md 和 README.md，先运行演示，再根据我的需求执行视频工作流。缺失模块如实报告，不发布视频。」

## 文档
- [AGENTS.md](AGENTS.md)：AI 执行指令
- [WORKFLOW.md](WORKFLOW.md)：九阶段生产流程
- [rules.md](rules.md)：质量硬规则
- [STATUS.md](STATUS.md)：实际交付状态和待修复问题

## 原始项目
原始代码和补充素材 ZIP 尚未导入。当前不是完整生产包。需将原始代码按目录导入，核查许可并修复实际依赖，再验证每种制作方式；大媒体按权限单独共享。不能把测试音调当作正式配音，也不能把设计文档当作已实现功能。
