# 任务目录

当前没有业务任务。架构师收到真实需求后按模板创建 `T0001` 起的任务。

每个任务目录包含 `brief.md` 与 `task.json`；实施后有 `submissions/`，审查后有 `reviews/`。任务清单由 `python scripts/workflow.py next` 从 `T*/task.json` 读取，状态字段不另维护第二份看板。
