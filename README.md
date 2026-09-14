# SoftReg · 软著全流程 Skill

一个从零到下证的软件著作权（软著）全流程 coding agent skill：**没有项目时引导开发可登记的真实软件 → 从真实项目生成全套合格申请材料 → 引导官网提交 → 跟踪进度与补正**。

人的动作只有四个：实名、收验证码、签字/盖章、传扫描件。其余全部由 skill 引导 agent 完成，每个关键节点停下来等你确认。

## 能力总览

| 阶段 | 能力 |
|---|---|
| Phase 0 项目工厂 | 选题引导、命名规范（xxx系统/软件 + V1.0 全局统一口径）、开发硬指标（非空代码 ≥3200 行、可运行 demo 供截图、无第三方版权内容混入） |
| Phase 1 材料工厂 | **代码鉴别材料.pdf**：单文件、60 页精确（前30+后30，页码连续 1–60）、每页 52 源码行（≥50 合规）、页眉一致、字号/行距按最差页自适应、超长行软折；**操作手册.pdf**：业务理解先行、4 轮自检（厚度/AI 味/制式模板/技术黑话）、截图嵌入；**申请表信息.txt**：25 字段对照 + 官网字符硬约束（50/100/500~1300） |
| Phase 2 提交教练 | 官网 R11 六步向导逐步引导（2026-09 官网实证）、字段对照、单 PDF 上传、验证码 1 小时窗口纪律、签章页手抄承诺引导 |
| Phase 3 进度管家 | 60 日审查期跟踪、30 日补正期提醒、补正意见→阶段回路由表 |

提交前对每份 PDF 自动体检：页数、页眉、页码连续性、文字层、每页行数、空白页。

## 安装

```bash
git clone https://github.com/tangjunyou/SoftReg.git
```

把 `.agents/skills/ruanzhu-autopilot/` 复制到你的 coding agent 的 skill 目录：

```bash
# Claude Code（全局）
cp -R SoftReg/.agents/skills/ruanzhu-autopilot ~/.claude/skills/

# 或项目级（仅该项目生效）
cp -R SoftReg/.agents/skills/ruanzhu-autopilot <你的项目>/.claude/skills/
```

要求 Python 3.10+；首次使用会自动在当前项目创建 `.venv` 并安装依赖（reportlab、pypdfium2、python-docx、Pillow）。

## 使用

在打开目标项目（或空目录）的 agent 会话里直接说：

```
用 ruanzhu-autopilot 给这个项目生成软著申请材料
```

或从零开始：

```
我没有项目，帮我从零开始申请一个软著
```

## 与上游 [SoftwareCopyright-Skill](https://github.com/Fokkyp/SoftwareCopyright-Skill) 的差异

本项目基于上游 v1.3（MIT）修复并扩展，核心变化：

- **修复** [#26](https://github.com/Fokkyp/SoftwareCopyright-Skill/issues/26)：放弃 Word 排版链路，reportlab 直接渲染 PDF，物理页数精确（上游 30 逻辑页在 Word 中实际 40 张）
- **修复** [#27](https://github.com/Fokkyp/SoftwareCopyright-Skill/issues/27)：官方上传槽为单文件，直接产出合并后的单个 PDF（页码连续 1–60）
- **修复** [#28](https://github.com/Fokkyp/SoftwareCopyright-Skill/issues/28)：字体全部内嵌（Courier New + Arial Unicode 子集），无主题字体依赖
- **新增** Phase 0 项目工厂 / Phase 2 提交教练 / Phase 3 进度管家，覆盖从选题到下证全流程
- **新增** `pdf_check.py` 提交前体检与官方字段口径实证校准（含 2026-09 官网填报页实测）

## 合规边界（内建于 skill，不可关闭）

1. AI 辅助编写代码：允许（行业常态）；登记的软件必须真实存在、真实可运行。
2. 文档鉴别材料必须经用户人工深度润色——官方 AIGC 审查重点即纯 AI 文档。
3. 实名、短信授权码、签章必须用户亲手完成；本 skill 只引导、只核对，不伪造、不绕过、不做批量。

## License

[MIT](LICENSE) · 衍生自 [Fokkyp/SoftwareCopyright-Skill](https://github.com/Fokkyp/SoftwareCopyright-Skill)（MIT）
