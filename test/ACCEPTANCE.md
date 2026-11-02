# MathSheetPress · 验收记录（2026-11-03）

方法：种子缺陷验收——引擎的核心主张是「答案键被独立证明」。验收用**第三条路径**（Python eval 直算转写后的表达式）复核表达式题、用引擎独立验证器复核全部题，并植入 1 条被篡改的答案验证闸门能且仅能抓住它。

终验结果：**9/9 PASS**（`acceptance_results.txt` 为真跑记录）

- 计数：4 卷 × 12 题 = 48 题
- 全书零重复题（48 unique / 48）
- 验证器与每条印刷答案一致（48/48）
- 第三路径 eval 复算表达式题 21 道，0 分歧
- 负控制：篡改 1 条答案 → 闸门恰标记 1 条
- PDF 为 612×792pt，页数 = 标题页 + 4 卷 + 答案键 = 6 页
- 固定 seed 完全可复现
- Arithmetic 档题型不越档（kinds ⊆ {expr, pct}）

本地包验证：PyInstaller 本机实构建成功（Linux 旁证，dist 产出 MathSheetPress 可执行＋_internal）；Windows 包由仓库 Actions 构建（待主会话建仓触发）。

样本：`sample_book.pdf`（3 卷 × 12 题，Mixed，seed 42）。
