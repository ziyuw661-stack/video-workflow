# 在成员电脑上启用定时生产

首次完整成片由成员验收后，用通过验收的固定 Git 提交和固定虚拟环境。配置 `production_accepted: true` 以及 `schedule`，例如 `{"collect":"09:00","generate":"09:30","report":"10:30"}`，时区是个人配置的 IANA `timezone`。可安排不需要采集的审核文稿队列：配置 `scheduled_spec` 和 `scheduled_evidence`，相对于个人配置文件；相同文稿不会每日重复做。自动取题时，需预置对应该批选题的 `topic_reviews` 与已查证的证据；取到无证据的题不会继续制作。

`python workflow.py --profile /绝对路径/account.json schedule` 输出确切命令参数；用任意调度器每五分钟调用，实际运行用 `run` 命令而非 `schedule`。计划本身不在仓库或后台替成员安装，仓库也不会自动运行 GitHub Actions 发布。

- Windows：任务计划程序用当前登录用户运行；程序填写虚拟环境的绝对 `python.exe`，参数填带引号的 `workflow.py --profile 路径 run`，重复间隔 5 分钟，进程已运行时不另起实例。
- macOS：使用 `~/Library/LaunchAgents`；把输出的 `argv` 作为 plist 的 `ProgramArguments`，设置 `StartInterval=300`，分别设置标准输出和错误日志。安装后检查一次实际触发。
- Linux：当前用户 crontab 使用 `*/5 * * * *`，将 `argv` 的每项作为参数正确引用，可在本机受保护的包装脚本里载入环境中的 API Key。不把密钥写到仓库、日志或同步目录。

当天同一阶段只触发一次；当天错过可补跑生产，不会补跑发布；前序失败不触发生成。失败或崩溃标记保留，先检查日志、实际阶段输出及后台进程，再由成员手动重跑，不盲目清除发布状态。手动重试生成使用新 job ID。远端上传结果不明确时，停下来进 Studio 核对，不自动再次上传。
