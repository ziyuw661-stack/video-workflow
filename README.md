# 团队 AI 自动化视频生产工作流

目标：成员把本仓库和原有生产项目交给自己的 AI，在自己的电脑独立生成完整视频及发布包，而非测试片。固定九步流程，AI 自主选择合适制作方式，也支持指定与自定义。免费优先，无中央服务器。

## 首次使用
1. 读取 AGENTS.md、WORKFLOW.md、rules.md 及 [原始 v3.1 规范](reference/WORKFLOW-v3.1.md) 第十节。
2. 当前仓库尚未导入生产代码。先将原始 video-workflow-v3-1.zip 和 video-workflow-projects-v3-1.zip 解压到本地隔离目录，核对原始目录、依赖、许可及凭证，按原有目录导入生产文件。不要覆盖本仓库入口文档；原文另存 reference/。大型媒体单独保存在本地，不必提交 Git。
3. 确认账号方向、受众、语言、声线、风格和平台；AI 自主调研关键词及对标账号。声线、风格首次小样确认后直接制作完整视频。
4. 按原有生产入口选择实际可用的路线，检查真实参数、素材及依赖后执行。优先使用原脚本；不得编造统一命令或用色块测试代替成片。

## 原始规范列出的生产入口（导入后需核实）
|方式|入口|输入|
|---|---|---|
|PPT 长片|core/scripts/build_ppt.py + core/scripts/pipeline.py|video.json、PPT、按页配音|
|白板|examples/landlord-method-v8/build_v8.py|script_v8.json、配音、素材；每期定制|
|竖屏|core/scripts/build_vertical_recut.py|横屏项目目录；检查是否为固定案例|
|热点|examples/nvda-hotspot/build_v3.py|script.json、真实画面、按句配音|
|课程动画|examples/greeks-course/greeks_full_a.py 或 render.py|分镜、音频、姿势图|
|配音|core/scripts/tts_qwen3.py|文字、获授权参考音和逐字稿|

每条正式任务输出完整 MP4、SRT、封面、发布文案、来源及验收记录。按用户平台和语言选择画幅及长度，不强制双版。默认不公开发布。白板元素实际对应配音最短 1.2 秒为硬规则。

## 使用指令
「按本仓库原有生产规范，结合本地原始项目，帮我完成一条正式视频。先检查现有代码和素材，修复缺失依赖；自动选题并制作成片，不能用技术测试代替。不能执行的步骤如实报告。」

## 文档及状态
- [AI 执行规范](AGENTS.md)
- [九步流程](WORKFLOW.md)
- [质量规则](rules.md)
- [白板原始规则](reference/whiteboard-rules.md)
- [实际状态](STATUS.md)

demo.py 仅为可选的 FFmpeg 环境诊断，不能作为生产入口、样片或质量证明。当前未完成代码导入与端到端验证，不得称为正式可运行生产包。
