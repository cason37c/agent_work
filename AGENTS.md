# Git 驱动的 Agent 协作

本仓库由人类提出需求，架构师 Agent 编写规格、发布任务并验收，编码 Agent 实现任务。默认顺序执行，一次一个活动任务。

开始工作时先读 [README.md](README.md) 和 [协作协议](.agents/skills/architect-orchestrator/references/workflow.md)。

- 架构师：读取 [.agents/skills/architect-orchestrator/SKILL.md](.agents/skills/architect-orchestrator/SKILL.md)。
- 编码 Agent：读取 [docs/agents/implementer.md](docs/agents/implementer.md)。
- 配置以 [docs/project/config.json](docs/project/config.json) 为准；任务状态以主分支 `docs/tasks/T*/task.json` 为准。
- 新功能、需求变更、实施报告、审查意见与完成结论均进入 Git。聊天里影响实现的决定应先写入规格再交接。
- 任务规格绑定提交 SHA；审查绑定代码提交 SHA。只有架构师可以作出 `ACCEPTED`、`DONE` 结论。
- 向主分支写入工作流元数据前先同步，修改后运行 `python scripts/workflow.py validate`；以普通 fast-forward push 交接。任务代码写入任务分支。
- 保留现有用户修改，按任务范围提交文件；远程拒绝推送时重新读取队列和历史。禁止通过强制推送覆盖其他参与者。

这些文件约束角色行为，不提供运行进程、模型账号、定时唤醒或身份认证。使用 Git 托管平台的权限与分支保护落实访问控制。
