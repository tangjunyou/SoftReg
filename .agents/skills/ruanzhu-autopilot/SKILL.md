---
name: ruanzhu-autopilot
description: >
  软件著作权（软著）全流程自动助手：没有项目时引导开发可登记的真实软件（Phase 0），
  从真实项目生成全套合格申请材料——代码鉴别材料单 PDF（60 页精确、每页≥50 行、页眉一致）、
  操作手册 PDF、申请表信息（Phase 1），引导官网 R11 在线填报、上传、短信授权、签章提交（Phase 2），
  以及提交后的进度跟踪与补正应对（Phase 3）。
  用户提到 软著、软件著作权、申请软著、软著材料、软著申请资料、代码鉴别材料、程序鉴别材料、
  操作手册、著作权登记、R11、软著提交、软著补正、下证 等任何相关意图时都必须使用本 skill，
  即使用户没有明确说"用 skill"。
compatibility: >
  Python 3.10+（推荐项目 .venv）；依赖 reportlab、pypdfium2、python-docx、Pillow。
  首次使用运行 scripts/setup_env.sh 或按 环境检查 手动建 venv。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
metadata:
  short-description: 软著全流程：造软件→出材料→引导提交→跟进度
  version: "2.0"
  upstream: 基于 Fokkyp/SoftwareCopyright-Skill v1.3（MIT）修复扩展
---

# 软著全流程 Autopilot

输入"我想要一个软著"，输出"电子证书"。人的动作只有四个：实名、收验证码、签字、传扫描件——每个断点本 skill 停下来手把手引导。

## 合规红线（任何阶段不得越过）

1. **AI 写代码可以**（行业常态）；登记的软件必须真实存在、真实可运行。
2. **文档材料必须人工深度参与**：操作手册草稿由 AI 生成后，用户必须实际改写润色至少一轮；官方 AIGC 审查重点就是纯 AI 文档，检出即补正甚至驳回。
3. **实名、短信授权码、签章必须用户亲手完成**：本 skill 只引导、只核对，绝不伪造、绝不绕过（无打码、无代签、无批量账号）。

## 阶段路由（每次先判断用户在哪）

| 用户状态 | 进入 | 文档 |
|---|---|---|
| "没有项目，帮我做一个能申请软著的" | Phase 0 项目工厂 | `references/phase0_project_factory.md` |
| 有真实项目，要材料 | Phase 1 材料工厂 | 本文件 + `references/*_rules.md` |
| 材料齐了，要提交 | Phase 2 提交教练 | `references/phase2_submission_guide.md` |
| 已提交，问进度/收到补正 | Phase 3 进度管家 | `references/phase3_progress.md` |

判断依据：`软件著作权申请资料/` 目录是否存在及其中产物（草稿、正式资料、生成报告）。

## 环境准备

首次使用时检查并创建 venv（项目根 `.venv`）：

```bash
bash ${SKILL_DIR}/scripts/setup_env.sh   # 无则按 python3 -m venv .venv && .venv/bin/pip install reportlab pypdfium2 python-docx pillow pypdf
```

之后所有脚本统一用 `.venv/bin/python` 执行。缺字体（Courier New / CJK TTF）时停下告知用户。

## Phase 1 · 材料工厂（核心流程）

输出目录固定为当前工作目录下 `软件著作权申请资料/`：

```text
软件著作权申请资料/
├── 草稿/            业务理解、申请表信息、代码文件选择、操作手册(md 供人工润色)
├── 截图/            手册配图（自动截取或用户放入 用户截图/ 后整理）
├── 用户截图/
└── 正式资料/        代码鉴别材料.pdf、操作手册.pdf、申请表信息.txt、生成报告.md
```

### 步骤 1 · 定位项目

扫描当前目录找项目根（避开本 skill、输出目录、node_modules、构建产物、隐藏目录）。多个候选必须停下让用户选（门禁 `project`）。

### 步骤 2 · 分析项目

```bash
.venv/bin/python ${SKILL_DIR}/scripts/analyze_project.py --project <项目目录> --out 软件著作权申请资料/analysis/project.json
```

### 步骤 3 · 业务理解（模型研判，不许脚本拍板）

```bash
.venv/bin/python ${SKILL_DIR}/scripts/generate_business_context.py \
  --project <项目目录> --analysis 软件著作权申请资料/analysis/project.json \
  --software-name "<软件全称>" --out-dir 软件著作权申请资料/草稿
```

模型阅读证据（README、路由、页面、接口、必要源码）后产出业务理解模型稿（字段口径见 `references/business_understanding_rules.md`），再带 `--model-context` 重跑生成 `草稿/业务理解.md`。**门禁 `business`**：用户确认行业、目标用户、核心功能、申请口径后才继续。

### 步骤 4 · 申请表字段

```bash
.venv/bin/python ${SKILL_DIR}/scripts/generate_application_info.py \
  --analysis ... --code-manifest ... --business-context 软件著作权申请资料/草稿/业务理解.json \
  --software-name "<软件全称>" --version "V1.0" --out-dir 软件著作权申请资料/草稿
```

字段口径、字符硬约束（50/100/500~1300）见 `references/application_fields.md`。**门禁 `application-fields`**：用户补全硬件/系统环境、著作权人、日期并确认。软件全称与版本号一经确认即全局唯一口径。

### 步骤 5 · 代码文件选择

```bash
.venv/bin/python ${SKILL_DIR}/scripts/propose_code_selection.py \
  --project <项目目录> --analysis ... --out-dir 软件著作权申请资料/草稿
```

模型阅读候选清单后填写 `草稿/代码文件选择.json`（selected/model_reason，可选 start_line/end_line），选择规则见 `references/code_selection_rules.md`。**门禁 `code-selection`**：用户确认后记录。

### 步骤 6 · 代码鉴别材料 PDF（单文件、页数精确）

```bash
.venv/bin/python ${SKILL_DIR}/scripts/build_code_pdf.py \
  --project <项目目录> --selection 软件著作权申请资料/草稿/代码文件选择.json \
  --software-name "<软件全称>" --version "V1.0" \
  --out 软件著作权申请资料/正式资料/代码鉴别材料.pdf
```

行为：非空行 ≥3120 走前 30 页 + 后 30 页（页码连续 1–60）；不足则全部提交模式。字号/行距按最差页自适应（7pt/11pt → 6pt/8pt 阶梯），装不下会 WARN 并建议剔除超长行文件。输出 `代码鉴别材料.pdf.manifest.json` 记录每个文件的行段与页范围——最后一行必须是完整语句（闭合的 `}` 或 `return`），不闭合时回到步骤 5 调整选择。

### 步骤 7 · 操作手册草稿 + 人工润色

```bash
.venv/bin/python ${SKILL_DIR}/scripts/generate_manual_draft.py \
  --analysis ... --business-context ... --software-name "<软件全称>" --version "V1.0" \
  --out-dir 软件著作权申请资料/草稿
```

结构要求见 `references/manual_structure.md`（中文大写序号章节、相关文档表格、面向普通用户、无技术黑话、截图预留可见）。**合规红线 2 在此落地**：草稿生成后必须明确要求用户通读并实际修改（润色措辞、补充真实使用细节），把用户的修改回合记录进 `草稿/手册润色记录.md`；用户明确拒绝修改时，在生成报告中注明 AIGC 风险自担。**门禁 `markdown`**。

### 步骤 8 · 截图

**门禁 `screenshot-method`**：Chrome DevTools MCP / agent 桌面控制 / 用户自行截图 / skip 四选一。用户截图放入 `用户截图/` 后：

```bash
.venv/bin/python ${SKILL_DIR}/scripts/capture_screenshots.py \
  --manual-dir 软件著作权申请资料/用户截图 --out-dir 软件著作权申请资料/截图
```

截图引用补入手册 md。跳过截图则保留可见的截图预留文字。

### 步骤 9 · 操作手册 PDF

```bash
.venv/bin/python ${SKILL_DIR}/scripts/build_manual_pdf.py \
  --manual 软件著作权申请资料/草稿/操作手册.md \
  --images-dir 软件著作权申请资料/截图 \
  --software-name "<软件全称>" --version "V1.0" \
  --out 软件著作权申请资料/正式资料/操作手册.pdf
```

### 步骤 10 · 双体检 + 生成报告

```bash
.venv/bin/python ${SKILL_DIR}/scripts/pdf_check.py --pdf 软件著作权申请资料/正式资料/代码鉴别材料.pdf \
  --software-name "<软件全称>" --version "V1.0" --expect-pages 60
.venv/bin/python ${SKILL_DIR}/scripts/pdf_check.py --pdf 软件著作权申请资料/正式资料/操作手册.pdf \
  --software-name "<软件全称>" --version "V1.0"
```

任一 FAIL 停下修复。全过后写 `正式资料/生成报告.md`（模式、页数、布局、体检结果、用户润色回合、遗留风险）与 `申请表信息.txt`。然后引导进入 Phase 2。

## 门禁纪律

所有门禁使用 `confirm_stage.py --stage <名> --note "<确认内容>"` 留痕；未留痕不得进入下一步。即使处于自动模式，也必须把 STOP_FOR_USER 与 NEXT_ACTION 原样告知用户并等待输入。禁止"未选择则默认继续"。

## 版本一致性（最高优先级不变量）

软件全称、版本号在申请表信息、代码 PDF 页眉、手册 PDF 页眉、手册正文、截图内容中**逐字符一致**；有无 V 以申请表为准。每次正式生成前重新从 `草稿/申请表信息.md` 读取口径。
