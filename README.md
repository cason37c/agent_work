# 架构师 Agent 与 Git 任务协作

你提出想法，架构师统一梳理需求、解释技术选型，再把需求说明书、设计文档、任务单和验收标准提交到 Git；编码 Agent 从 Git 领取任务并提交实现；架构师审查指定提交，验收合入后释放下一项任务。

## 开始使用

已安装个人入口时，在新窗口直接说：

> 架构师模式，我想做一个……

需求沟通、技术选型解释和接受用户修正的方式见 [协作约定](docs/project/working-agreement.md)。需求不完整也可以开始，架构师负责继续梳理。

独立业务项目各用一个 Git 仓库；`agent_work` 保存公共规则、工具和 [项目索引](docs/projects.json)。新建、选择、恢复与归档项目遵循 [多项目管理规则](docs/project/multi-project.md)。只说“架构师模式”时先加载索引；目标未确定时等待需求或项目选择。现有产品的新功能继续在其原仓库开发。

下面的仓库入口适用于尚未配置个人技能的环境：

```text
git clone https://github.com/cason37c/agent_work.git
cd agent_work
python scripts/workflow.py validate
python scripts/workflow.py next
```

需要 Git 和 Python 3.10 或更新版本，脚本只使用 Python 标准库。当前仓库提供协作框架，尚无业务任务。`next` 是只读建议，不会领取任务或启动模型。

将以下提示交给负责架构的模型，并让它能够访问管理仓库及目标项目仓库：

```text
你是架构师与验收负责人。先同步 agent_work，读取 AGENTS.md 和
docs/project/multi-project.md，通过 docs/projects.json 确定目标项目。
在目标仓库读取 AGENTS.md 和 .agents/skills/architect-orchestrator/SKILL.md。
我接下来会描述需求。请将需求、设计、任务和验收规则写入目标仓库并推送，
交给编码 Agent 实现；对每次提交做审查并留下可追溯的验收结论。
```

将以下提示交给另一个负责实现的模型，并填入目标仓库地址；项目内的任务 ID 单独使用不足以定位任务：

```text
你是本项目的编码 Agent。目标仓库：<目标项目仓库地址>。
先核对并同步目标仓库，读取 AGENTS.md 和
docs/agents/implementer.md，再运行 python scripts/workflow.py next。
按协议领取一个任务，从任务绑定的 Git 规格实现、验证并提交到任务分支，
将主分支状态更新为 IN_REVIEW 后交接。审查通过并合入、标记 DONE 后再领取下一项。
若需返工，继续当前任务；若等待审查，保留交接信息并在外部运行环境再次唤醒时继续。
```

支持技能的环境也可加载仓库中的 `.agents/skills/architect-orchestrator`，以 `$architect-orchestrator` 调用。其他模型按上述路径读取 Markdown 即可，不依赖特定厂商。

## 文件入口

| 文件 | 用途 |
| --- | --- |
| [架构师技能](.agents/skills/architect-orchestrator/SKILL.md) | 需求、设计、拆解、审查与后续功能管理 |
| [协作约定](docs/project/working-agreement.md) | 单一架构师模式、技术选型解释和用户修正 |
| [多项目管理](docs/project/multi-project.md) | 项目选择、独立仓库初始化、恢复和归档 |
| [项目索引](docs/projects.json) | 项目标识、名称、仓库地址与生命周期 |
| [个人架构师入口源码](skills/architect/SKILL.md) | 安装到个人 skills/architect 的启动规则 |
| [协作协议](.agents/skills/architect-orchestrator/references/workflow.md) | 状态机、分支交接、验收门槛和异常恢复的权威规则 |
| [编码 Agent 规则](docs/agents/implementer.md) | 领取、实现、提交、返工与继续下一任务 |
| [需求说明书](docs/features/F0001-agent-workflow/requirements.md) | 这套协作机制的需求和验收项 |
| [设计文档](docs/features/F0001-agent-workflow/design.md) | Git 存储、职责、提交顺序及工具边界 |
| [模板](.agents/skills/architect-orchestrator/assets/templates) | 功能、任务、实施、审查与变更文档 |
| [项目配置](docs/project/config.json) | 控制分支、远程和顺序执行规则 |

## 验证程度

这是一套为本项目建立的初版协作框架。分支交接、合入前审查、代码变化后重新审查等工程机制与 [GitHub 分支保护的做法](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) 一致。

本仓库目前的验证证据是 17 项自动测试和一次独立 Agent 的完整交接试运行，详情见 [交付检查](docs/reviews/F0001-bootstrap.md)。尚未经过长期、多项目或多种模型运行器的实际使用验证；真实业务接入后，架构师应根据出现的问题修改规则、补充必要验证，再提交到 Git。测试通过也不等同于已经具备后台调度、远程认证和平台权限控制。

## 工作节奏

```text
人类需求 → 需求/设计 → READY → 领取并实现 → IN_REVIEW
                                           ↓
下一项 ← DONE ← 合入并验证 ← ACCEPTED ← 架构师审查
                                           ↓ 不通过
                           再次审查 ← 返工 ← CHANGES_REQUESTED
```

顺序执行以项目仓库为边界，表示同一项目的前一任务 `DONE` 后才能领取下一项。跨项目调度由用户或宿主执行器安排。需求不充分时先形成 `DRAFT`；需要人类决定的阻塞写入 Git 后提问，不用猜测替代关键产品决定。普通实施选择由 Agent 自行处理。

## 检查与运行边界

```text
python scripts/workflow.py validate
python scripts/workflow.py next
python -m unittest discover -s tests -v
```

每次领取前先 `git fetch origin`、切换到 `main` 并 `git pull --ff-only origin main`。`next` 检查本地是否与已获取的远程主分支一致；它不会主动联网，无法发现尚未 fetch 的更新。最终以领取状态提交能否成功 push 为准。

结构检查可以发现缺失规格、依赖循环、并行领取、审查 SHA 不匹配及不完整的完成记录。它无法判断实现是否正确、测试证据是否真实，也不能验证填入的角色身份；这些属于架构师审查和托管平台权限的职责。

本仓库没有后台调度器。两个模型需要分别由人或外部执行器启动；持续运行的执行器可在唤醒后读取队列继续。Git 提交不会自行唤醒另一个模型。

接入业务项目时由架构师先准备独立项目仓库和协作文件，再发布首个编码任务。已有项目应合并原有 `AGENTS.md` 和项目约束，按实际环境调整 `config.json`；具体步骤见多项目管理规则。公共规则升级通过各项目自己的 Git 变更引入。生产发布、删除数据等操作由具体项目另行定义授权。
