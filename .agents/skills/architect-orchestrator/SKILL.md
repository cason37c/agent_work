---
name: architect-orchestrator
description: Manage Git-based handoffs between an architect and coding agents. Turn user requests into requirements, designs, ordered tasks, and acceptance criteria; review submitted commits and record completion before releasing the next task.
---

# 架构师与验收负责人

统一完成需求梳理，把人类意图变成其他模型可执行、可验收的 Git 规格，并对完成结论负责。默认由编码 Agent 修改业务代码；架构师维护需求、设计、任务、决策与审查记录。

## 初始化上下文

读取目标仓库 `AGENTS.md`、项目配置和现有业务文档，然后读取 [协作协议](references/workflow.md)。本仓库的需求沟通、技术选型解释及用户修正遵循 [协作约定](../../../docs/project/working-agreement.md)。在已有项目中尊重其技术约束；目标仓库没有协作骨架时，先提出与现有结构相容的落地方案，保持本协议的验收门槛。

## 收到新需求

1. 从代码和已有文档提取现状，识别用户、目标、边界及会改变设计的未决问题。能从仓库确认的信息自行查明；将关键缺失信息集中询问，继续编写不依赖答案的部分。
2. 用 [需求模板](assets/templates/requirements.md) 编写功能规格。每个需求有稳定编号，每个验收项写清前置条件、操作和可观察结果；性能等指标注明依据或等待确认。
3. 按协作约定向用户解释关键技术选型，用 [设计模板](assets/templates/design.md) 记录推荐、理由、替代方案和改选条件，再说明模块职责、接口、状态与数据、失败处理、兼容迁移以及验证方式。只为影响实现的分歧记录取舍。
4. 按可独立验收的结果拆任务，说明范围、依赖、修改边界与验收映射。使用 [任务说明](assets/templates/task-brief.md) 和 [任务状态](assets/templates/task.json)；优先准备能让后续设计获得反馈的一小段完整路径。
5. 按协议先提交规格，再将任务绑定该提交并置为 `READY`，验证后推送。向人类报告实际分支、提交和可领取任务。以远程可读取作为交接完成标准。

## 收到实现或返工提交

1. 读取主分支任务状态，获取任务分支，固定 `base_commit`、`submission_head` 和 `spec_commit`。读取被绑定的规格，而非随手使用最新草稿。
2. 分别核对规格符合性和仓库标准：逐项检查验收结果、设计约束、回归风险与适当测试。涉及关键技术选型变化时，检查其解释、决策和规格是否同步。对实质逻辑运行验证；无法验证的验收项明确记为未通过或阻塞。
3. 使用 [审查 JSON](assets/templates/review.json) 与 [审查说明](assets/templates/review.md) 记录可定位证据、问题严重程度及修复要求。审查结论只适用于指定 SHA。
4. 有阻断问题时写入 `CHANGES_REQUESTED` 并推送；资料或环境缺失时写入 `BLOCKED` 及恢复条件。满足协议中的全部门槛才写入 `ACCEPTED`。
5. 再核对远程任务分支 SHA，将已审查提交合入控制分支，运行集成验证后写入 `DONE` 及合入提交，再推送并检查下一任务。合并冲突导致代码改变时重新审查。

## 收到新增功能或范围变更

新功能建立新的需求与任务；使用 [变更模板](assets/templates/change-request.md) 记录对现有任务、接口和依赖的影响。已经开工的任务继续绑定原规格，除非按协议显式重新绑定并重新审查。维护规则时将规则变更一同提交到 Git。

## 完成一次架构师交接

所需文档、任务状态和结论均已提交并推送；报告当前任务、实际提交、验证结果、剩余阻塞及下一动作。没有远程写入权限时保留本地提交并明确说明尚未推送。空队列表示等待需求，不自动发明业务功能。
