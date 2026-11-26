# 团队 AI 自动化视频生产工作流

以 PDF v3.0 为准。每个成员独立运行、独立配置和授权。看[实现与验收对照](docs/pdf-v3-alignment.md)了解当前覆盖范围。

## 首次启动

1. 克隆此公开仓库，使用 Python 3.10+、带 libx264 和 ass 的 FFmpeg/ffprobe，在自己的虚拟环境安装依赖。
2. 将 `configs/account.example.json` 复制到本机非版本控制目录。配置账号 ID、IANA 时区、工作区与非同步状态目录，分别保管密钥。成员确认目标、声线、风格和授权；AI 提供关键词/对标策略，成员不必手动搜。
3. 在仓库根目录运行，各处 `ACCOUNT.json` 替换成个人配置路径：

```sh
python -m pip install -r requirements-workflow.txt
python -m unittest discover -s tests
python workflow.py --profile ACCOUNT.json setup
python workflow.py --profile ACCOUNT.json generate first-sample --sample --spec examples/video.json
python workflow.py --profile ACCOUNT.json qc first-sample
```

示例默认用 Edge TTS。如果它不可用，先检查服务和许可；也可按场景提供 `audio` 与实际 `cues: [[开始秒,结束秒,文本]]`。正式任务可选经试听的 Kokoro：安装 `requirements-kokoro.txt`，设置 `tts_provider: "kokoro"`、`kokoro_lang`、`kokoro_voice`、`tts_speed`，按 [Kokoro 文档](https://github.com/hexgrad/kokoro) 安装目标语言依赖。不得用静音或测试音冒充成片。

## 正式工作

- **collect**：把 YouTube Data API Key 通过本机环境变量 `YOUTUBE_DATA_API_KEY` 提供；按个人配置采集关键词、对标频道和趋势。或通过 `collect --import-json metadata.json` 导入允许使用的元数据。导入项需要 `platform, video_id, title, url`，可提供 `published, channel, duration, views, likes, comments`。同时传 `--reviews topic-reviews.json` 导入评分数组：`platform, video_id, match, relative, growth, recency, originality, feasible, source_allowed, near_duplicate`。权重遵循 PDF，评分 0–100，未知写 null；不是每条采集到的视频都可用于生产。账号库是 SQLite，工作区导出四份 Excel。
- **generate**：`generate JOB_ID --evidence EVIDENCE.json` 自动取合格未制作选题，用本机 Ollama（默认 `qwen3:4b`）写分镜；也可加 `--spec VIDEO.json` 使用已准备的文稿。证据数组每条包含 `id, url, claim, verified`，只在核实后写 true；自动取题时证据还需包含 `topic_key: "平台:视频ID"`。每个场景引用 `evidence_ids`。程序检查结构和引用，不能代替事实审阅。素材应来自可信、已授权路径，不下载未知视频。基础画面目前为图文轻动效，模块状态见 `modules/registry.json`。
- **qc / review**：先查看 QC，完整观看、试听并核查内容与权利。复制 `configs/review.example.json`，提交 `review JOB_ID --checklist REVIEW.json`。只有独立人工检查合格、分数至少 80 才批准；系统记录该版成片和发布包哈希。更改后需重新审核，样例不得发布。
- **schedule / run**：`schedule` 输出可交给系统调度器的参数；先验收完整成片再开启 [定时指引](docs/local-schedule.md)。阶段依赖上一阶段成功；生产调度不上传视频。
- **publish**：原生发布后用 `publish JOB_ID --url https://…` 回填；域名必须在个人配置允许列表中。YouTube 官方 API 路线先安装 `requirements-youtube.txt`、启用个人配置的 `youtube_enabled` 及正确 `youtube_channel_id`，然后本人完成 `youtube-auth --client CLIENT.json`。明确提供受众/生成内容披露后，批准的成片先 `publish JOB_ID --target youtube --private`。之后可以重复这个命令查询处理，不会重复上传；本人批准并显式启用 `allow_scheduling` 后，可为已处理完成、从未公开的私享视频新增 `publish JOB_ID --target youtube --at 2026-12-01T18:00:00+08:00`（用实际未来时间替换）。授权、频道、处理状态和批准不符即停。TikTok、抖音、小红书、视频号默认原生发布，不绕过平台风控。
- **report**：生成当日作业、质检、审核及发布状态；`report --metrics METRICS.json` 导入平台报表，字段 `job, views, ctr, retention, completion, likes, comments, shares`，没有数据写 null。实际同步状态须在 Drive for desktop 核对，不同步 SQLite、凭据、模型和缓存。

原有 `produce.py` 与 `collect.py` 仍可独立调用。生产目录生成 MP4、SRT、封面、发布包、原始配音、分镜、时间轴及 QC。见 [PDF 对照与缺项](docs/pdf-v3-alignment.md) 和 [执行规范](AGENTS.md)。

官方接口：[采集](https://developers.google.com/youtube/v3/docs/search/list) · [上传](https://developers.google.com/youtube/v3/docs/videos/insert) · [排期](https://developers.google.com/youtube/v3/docs/videos/update) · [Ollama](https://docs.ollama.com/api/chat)。
