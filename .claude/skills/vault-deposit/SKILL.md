---
name: vault-deposit
description: "Deposit a cross-project conclusion — session retrospective, adjudicated decision, durable lesson — into the personal knowledge vault (ObsidianVault) without leaving the project directory. Pointer-style: locate the vault, READ its AGENTS.md for current conventions (never cached here), write per those conventions, commit atomically and read back HEAD. Use at session wrap-up when the user says '值得存' or a durable cross-project takeaway exists (复盘/判例/拍板结论)."
---
# Vault Deposit（跨目录投递，指针式）

本 skill 是触发器 + 指路牌：**格式约定的单源永远是 vault 自己的 `AGENTS.md`**，本文件不缓存任何格式规范——缓存副本必然漂移。

## 定位 vault（依次尝试）

1. 环境变量 `$OBSIDIAN_VAULT_DIR`；
2. `~/.config/obsidian-vault-path` 文件内容（一行绝对路径）；
3. 已知默认：WSL `/mnt/d/ObsidianVault`。

找不到或不可写 → 明说"vault 本机不可达，未投递"，把内容暂留仓内（task notes / memory），提示用户；**不许**自造格式、写到别的目录、或假装投递成功。

## 协议（每次都完整走）

1. **Read `<vault>/AGENTS.md` 全文**（现场读，拿最新约定）；写会话复盘类，再对照 `素材/AI对话/` 最近一篇对齐模式。
2. 判断层次：原始采集 / 会话复盘 → `素材/`；判例、拍板结论、项目 rollup 更新 → 对应 `领域/` 笔记——**promote 到领域层须经用户确认**（AGENTS.md 有细则）。
3. 按约定写笔记 + `index.md` 一行 + `log.md` 追加一行（三件一体，缺一不算落库）。
4. **原子提交并读回**：write → add → commit 一气呵成，然后 `git log -1` 读回 HEAD——`/mnt/d` 是 9p 挂载写入不稳，只信 HEAD 读回，不信命令回显。
5. 会话中断没走到这步 → 接手会话开局补（全局记忆条款）。

## 反模式

- 投递成本超过"一条命令的心智负担"就会在压力下被跳过——保持轻，一次投一件事。
- 半成品、项目内部事实不进 vault（那是仓内 memory / task 产物的地盘）；只投"未来会被跨项目引用"的成品知识。
- 不要在投递时顺手重组 vault 结构——结构变更是 vault 自己会话的事。
