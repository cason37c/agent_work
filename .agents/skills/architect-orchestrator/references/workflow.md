# Git 协作协议 v1

本文件是状态与交接规则的单一权威来源。项目配置存于 `docs/project/config.json`，以下示例采用 `origin/main`。路径均相对目标仓库根目录。

## 1. 职责与事实来源

| 参与者 | 负责内容 |
| --- | --- |
| 人类 | 产品目标、关键业务取舍、所需账号与实际授权 |
| 架构师 | 需求梳理、范围与验收标准；技术选型解释和设计；依赖与任务发布；审查、合入、验收；规则维护 |
| 编码 Agent | 领取、实现、验证、实施报告、返工及提交审查 |

主分支的 `docs/tasks/T*/task.json` 是任务状态的事实来源。需求和任务契约读取 `spec_commit` 中的文件；审查读取 `submission_head` 对应的代码。聊天、PR 标题、模型的“已完成”陈述不能替代记录。

一次只允许一个活动任务。角色标识采用可区分的模型/会话标识；编码者与审查者应独立。文档规则与脚本不是身份认证，主分支保护、审核权限等需要在 Git 托管平台按团队环境设置。

## 2. 任务与文档

- 功能文档：`docs/features/Fxxxx-name/requirements.md`、`design.md`。
- 任务说明与状态：`docs/tasks/Txxxx/brief.md`、`task.json`。每个任务有明确验收编号；跨功能验收编号加功能前缀。
- 实施证据：任务分支的 `docs/tasks/Txxxx/submissions/round-N.md`。
- 审查记录：主分支的 `docs/tasks/Txxxx/reviews/round-N.json` 与可选 `.md`。新一轮审查新增文件保留旧结论。
- 架构决策：`docs/decisions/ADR-xxxx-name.md`；范围变化：`docs/changes/CR-xxxx-name.md`。

任务 JSON 的 `artifacts` 指向需求、设计和任务说明，路径必须位于仓库内。`acceptance_ids` 是本任务要满足的验收项；`requires` 是先决任务 ID。`priority` 数值越小越优先，同级按 ID 排序。模板中的示例编号要替换为真实内容。

`previous_owners` 保留接管前的编码者标识，接管原因记在控制提交中；任何参与过实现的 owner 都不能作为该任务的独立审查者。取消任务时增加非空 `cancellation_reason`。

所有非草稿、非取消任务绑定完整 `spec_commit` SHA；该提交必须包含任务契约与所引用规格。发布分两次提交：先提交完成的规格和任务说明，再提交绑定前一 SHA 的 `READY` 状态。这样无需把提交自身的 SHA 写回自身。

## 3. 状态机

| 转换 | 执行者 | 条件 |
| --- | --- | --- |
| DRAFT → READY | 架构师 | 规格完整、重要问题已决定、验收可执行、依赖已登记 |
| READY → IN_PROGRESS | 编码 Agent | 先决任务全部 DONE；无活动任务；领取状态已成功推送 |
| IN_PROGRESS → IN_REVIEW | 编码 Agent | 实现与证据已推送，记录固定的提交 SHA |
| IN_REVIEW → CHANGES_REQUESTED | 架构师 | 已提交绑定该 SHA 的问题和修复标准 |
| CHANGES_REQUESTED → IN_PROGRESS | 原编码 Agent | 读取本轮意见，继续同一任务，不另领取 |
| IN_REVIEW → ACCEPTED | 架构师 | 本节及第 6 节所有审查门槛满足 |
| ACCEPTED → DONE | 架构师 | 审查提交已合入、集成验证通过、记录合入 SHA |
| 未终结状态 → BLOCKED | 当前负责人 | 写明原因、所需信息与恢复前状态 |
| BLOCKED → 原状态 | 架构师 | 阻塞解除，重新核对规格/提交/依赖；记录恢复理由 |
| BLOCKED(原 ACCEPTED) → IN_PROGRESS | 架构师 | 集成失败需修复，保留失败证据并按第 6 节重新送审 |
| 未终结状态 → CANCELLED | 架构师 | 人类取消或明确范围调整，记录原因与依赖影响 |

活动状态为 `IN_PROGRESS`、`IN_REVIEW`、`CHANGES_REQUESTED`、`ACCEPTED`、`BLOCKED`。终态 `DONE` 与 `CANCELLED` 不重新打开；后续问题建立新任务，保留历史结论。被取消的先决任务不算完成，架构师必须重新规划依赖。

`BLOCKED` 必须保留 `blocked_from`；恢复时清理阻塞字段。编码 Agent 可报告阻塞，恢复/取消/验收由架构师决定。每次状态变化在提交说明中写清任务 ID 与原因。结构校验只检查当前快照，不证明历史转换或操作者身份。

## 4. 领取与分支

1. 使用干净工作目录 fetch 并同步控制分支，读取规则与任务，运行 `python scripts/workflow.py next`。本地未 fetch 的内容不具备实时性。
2. 得到 `CLAIM` 后，在控制分支仅修改该任务 `task.json`：填 `owner`、`branch`，将 `base_commit` 设为领取前主分支的完整 SHA，置为 `IN_PROGRESS`。验证后提交并普通 push。
3. 推送成功才算领取。两个执行者竞争时，只有成功 fast-forward push 的领取有效。失败者保留自己的本地工作，重新读取远程队列；不以自动合并、重放或强推重复领取。
4. 从已推送的领取提交创建 `task/Txxxx-short-name`。业务代码、测试、实施报告提交到该分支。`task.json`、项目配置、协作规则和需求契约由控制分支管理，任务分支保持这些文件不变；需要调整规格时交给架构师。

控制分支的任务状态允许编码 Agent 作领取、提交审查、开始返工、报告阻塞等限定更新。代码始终在任务分支。建议为控制更新和编码使用不同工作目录，以减少误提交。托管平台若要求所有变更走 PR，控制更新也通过 PR，合入成功后才视为领取或交接；不得绕过保护策略。

`base_commit` 是比较实现的固定基线；`spec_commit` 是契约快照，两者用途不同。领取后优先处理已有活动任务，不跳过待审查或阻塞任务去做下一项。

## 5. 实现与提交审查

编码 Agent 按固定规格实施，逐项验证验收要求并提交实施报告，内容包括改动、命令、结果、关键输出、环境和未验证项。测试失败或环境不足时如实记录，不能据此宣称验收通过。

先推送任务分支，再在控制分支更新 `task.json`：

- `status = IN_REVIEW`；
- `submission_head =` 已推送任务分支的完整 SHA；
- `implementation_report =` 该 SHA 内存在的实施报告路径；
- 新轮次提交时 `review = null`，保留磁盘中的旧审查文件；`integrated_commit = null`。

验证后提交并推送控制分支。已提交待审查的分支暂时冻结；任何新增提交都应重新登记 `submission_head` 并重新审查。编码者等待审查，不自行标记完成。返工沿用任务分支和 `base_commit`，为每轮新增实施与审查记录。开始返工时先读旧审查，再将状态恢复至 IN_PROGRESS 并清空 `review` 指针；旧审查文件继续保留。

## 6. 审查、合入与完成

架构师 fetch 任务分支，确认其远程 HEAD 与 `submission_head` 完全一致，读取固定规格及 `base_commit..submission_head` 的完整差异。审查至少覆盖四维：

| 维度 | 审查内容 |
| --- | --- |
| requirements | 每个验收项与实现/证据对应，边界与异常满足规格 |
| design | 接口、模块职责、数据与兼容处理符合设计或有已提交的新决策 |
| standards | 遵守项目规则，检查相关正确性、安全性与可维护性问题 |
| verification | 适当测试与必要构建通过；重要验收有可复核证据 |

审查 JSON 记录 `reviewed_head`、`reviewed_base`、独立 `reviewer`、四维结果、每项验收的证据及所有发现。问题优先级：P0 阻断/严重破坏，P1 高影响错误，P2 影响正确性或漏需求，P3 非阻断改进。P0–P2 必须修复；P3 只有记录明确接受理由才可带入后续任务。

只有四维全部 PASS、每个验收项 PASS 且证据非空、无未解决的阻断问题，才可给 `APPROVED` 并将任务置 `ACCEPTED`。缺少验证环境的关键验收应 `BLOCKED`，已有实现问题应 `CHANGES_REQUESTED`；无法验证不能写为 PASS。

再次 fetch 并比较远程任务分支 HEAD，确认仍为已审查 SHA。确认控制分支相对基线的变化不会引入未审查的集成风险，再通过保留历史的 merge commit 合入该 SHA。合入过程需解决业务代码冲突时，先在任务分支解决、重新提交审查；不得将改动直接当作已审查代码。

合入后按任务和项目配置执行集成检查。记录命令、结果及被测合入提交；成功后另起状态提交，将 `integrated_commit` 设为被测 merge SHA 并置 `DONE`，再推送控制分支。若集成失败，记录 `BLOCKED`、`blocked_from = ACCEPTED`，将失败 SHA、命令和结果写入独立 `reviews/integration-round-N.md` 并推送。需要修改实现时，架构师将状态转为 IN_PROGRESS，清空 blocker/review/integrated_commit/integration_evidence 字段，保留失败报告和旧审查文件；编码者沿任务分支修复，登记新 submission_head 并重新送审、合入和验证。若只是环境阻塞，解除后恢复 ACCEPTED 并重跑集成验证。必要时通过新的 revert 提交恢复，不改写共享历史。

`DONE` 必须有完整规格、实施报告、匹配提交的批准审查、主分支可达的合入提交，以及集成验证证据 `integration_evidence`。通过后再运行 `next`。此协议不等同于生产发布授权。

## 7. 变更、恢复与连续运行

- 新需求先更新文档再排队。READY 任务的规格更新要重新绑定；活动任务如范围改变，先进入 BLOCKED，记录变更、影响与新验收，重新发布规格 SHA。将 `base_commit` 更新为恢复前的控制分支 SHA，清除旧 submission/report/review/integrated/integration_evidence 字段，以新任务分支名恢复至 IN_PROGRESS 并推送，再从这个新的领取提交建立分支。旧分支保留，所需实现经检查后移植到新分支；旧结论留在历史中。
- 网络或认证失败时保留本地提交，明确区分“本地已提交”与“远程已交接”。权限恢复后先同步确认，避免覆盖远程新进度。
- 重启后从远程控制分支、任务分支与审查文件恢复，不依赖聊天记忆。历史任务分支有新提交但队列仍为旧 SHA 时先核对交接，架构师不审查漂移的分支。
- `next` 返回 CLAIM、RESUME、WAIT_REVIEW、INTEGRATE、BLOCKED 或 IDLE；只有 CLAIM/RESUME 指示编码动作。它不修改文件，不自动发消息或启动模型。
- 持续运行由人或外部执行器提供。等待期间遵守运行环境的等待/退出机制，下一次唤醒时重新 fetch；没有执行器时明确给出手动交接入口。
