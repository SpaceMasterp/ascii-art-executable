# B 部分缺口审计 + 上线前仓库体检

> 只读审计，未修改任何源码。审计对象：`ascii-art-executable_B`（B 的实现）、`samples/`（B 的样例）、
> 方案书 docx、`project-issues-for-PM.md`、`project_issues_narrative.md`、`ascii-art-executable_BF/F_对接说明.md`。
> 测试环境：`/tmp/b_venv`（Python 3.13.5 + Pillow 13.0.0 + pytest 9.2.0），**26 passed**。
> 说明：文档清单里的 `project-issues-narrative.md`（连字符版）**不存在**，仓库里只有 `project_issues_narrative.md`（下划线版），已按后者审计。
>
> **2026-11-04 更新：P0-1（max_w 默认 72）、P0-2（slogan 分支）、P0-3（鸭子类型 export_meta）、P2（侧车 `size`）、P1（.gitignore 补 `.DS_Store`）已修复，测试 26 → 38 全绿，详见 §六「修复前后对照」。**

---

## 一、结论摘要

1. **功能面已闭环，可以过 G1**：`build_grid` + 单宽 charset 校验 + `fg_rows` 掩码 + `export_meta/load_meta` + 3 组固定样例齐了，26 条测试全绿且从任意 cwd 都能跑（`cd /tmp && pytest <B>/tests` → 26 passed）。
2. **`max_w` 默认值没落实**：文档要求默认 72（PM §9 B①、PM:23 的 72×36 golden），代码仍是 `max_w: int = 80`（`grid.py:123`）。不传参实测 `width=80`、`meta["max_w"]=80`——D8 若照文档写 `build_grid(demo/cat.png)` 会拿到 80 宽，和 72×36 golden 对不上。
3. **Slogan 分支有两个必现缺陷**：① 长度 ≳48 字符的文本退化成 `72×2 / fg=0` 的空网格（`README.md:44-45` 还自称"长口号自动折成多行"）；② 长度 ≥256 字符时 `grid.py:138` 的 `Path(src).is_file()` 直接抛 `OSError: [Errno 63] File name too long`，不是 `ValueError`。
4. **接口冻结存在硬冲突**：B 的 `PixelGrid` 7 个字段（多 `max_w`）+ 3 个掩码方法，BF 的 6 个字段但多 `ShapeReport`/`DetectionReport`；两边互不包含。且 `export_meta` 用 `isinstance(grid, PixelGrid)` 硬判（`grid.py:348`），传 BF 版实例实测报 `ValueError: grid must be a PixelGrid, got PixelGrid`——A 冻任何一份都会打断另一边，必须先合并。
5. **仓库还不是 git 仓库**（无 `.git`、0 commit）；`.gitignore` 已挡 `.venv/`(40M)、`__pycache__/`、`*.pyc`、`.pytest_cache/`，但**漏 `.DS_Store`**（B 根那份 6148 B 会进首个提交）。

---

## 二、逐条对照表

状态取值：**已满足 / 部分满足 / 缺失 / 无需 B 负责**。"需不需要做"指 B 是否要动手。

| # | 要求（摘原文） | 出处 | 状态 | 证据 | 需不需要做 |
|---|---|---|---|---|---|
| 1 | `build_grid(src, charset, max_w) → PixelGrid`；输入 图像/Slogan → 字符网格；"尺寸受控，前景/背景标记清晰" | docx §六（三）表 2 B 行 | 已满足 | `grid.py:120-151`；`tests/test_grid.py:47`（test_returns_pixelgrid_with_consistent_shape） | 否 |
| 2 | PixelGrid "内含宽度、每格坐标及其前景/背景标记" | docx §六（二）第 2 段 | 已满足 | `shared/types.py:25-32`（GridCell）、`:43-54`（PixelGrid 字段） | 否 |
| 3 | "每个格子对应源码中的一个字符位，前景格标记为需占用、背景格标记为可留空" | docx §二（二）第 1 步 | 已满足 | `grid.py:173-180`（fg/level/ch 赋值）；`GridCell.fg/ch`；`test_fg_bg_marks_clear`（tests:62） | 否 |
| 4 | 骨架期验收："输入任意 PNG，程序能输出**尺寸受控**的字符网格并正确区分前景与背景" | docx §四（二）第 1 句 | 部分满足 | 宽度受控（`grid.py:165` `tw=min(g.width,max_w)`，`test_width_capped_by_max_w` tests:56）；**高度无上限**：50×2000 图 @72 → `50×1000`（实测）；白底黑图默认 `density=0.797`（需手动 `invert`） | 是（P1：`max_h` + 文档写清） |
| 5 | "支持自定义字符集与分辨率上限" | docx §五（一）B 段 | 已满足 | `charset` 参数 + `validate_charset`（`grid.py:69-101`）；`max_w` 校验 `_validate_max_w`（`:103-117`） | 否 |
| 6 | "补 charset 单宽白名单，13 条测试常绿" | PM:201（§9 B①）；PM:96（§3 第 5 条"1 格=1 字符、只可打印 ASCII、禁 Tab/CRLF/全角"） | 已满足 | `test_charset_accepts_printable_ascii`、`_rejects_tab`、`_rejects_cjk_and_emoji`、`_rejects_empty_and_non_str`、`_duplicates_are_deduped`（tests:139-186） | 否 |
| 7 | "确认 `grid_rows`/`fg_rows` 的写侧车格式与 **`max_w` 默认 72**" | PM:201 | **已修复**（默认 72） | 修复前 `grid.py` `max_w: int = 80`；修复后 `max_w: int = 72`（`grid.py:132`），`test_default_max_w_is_72` 断言 cat → 72×36/1126 且 `meta.max_w=72` | 否 |
| 8 | "13/13：B 的图案网格测试全部通过……G1 判据 = `tests/test_grid.py` 13/13" | PM:22、PM:131 | 已满足（现在是 26） | 13 条原测试一行未改，新增 13 条；`pytest -q` → **26 passed**；从 `/tmp` 跑同一套也 26 passed（不依赖 cwd） | 否 |
| 9 | "测试必须能 `python3 tests/xxx.py` 直接跑" | PM:144 | 已满足 | `tests/test_grid.py:291-311` 自带 standalone runner；`python3 tests/test_grid.py` → 26/26 | 否 |
| 10 | 侧车至少要有 `grid_rows`（期望字形）、`fg_rows`（前景掩码）；"只存一个会丢掉这格到底是不是前景" | narrative:231,233；PM:95 | 已满足 | `export_meta`（`grid.py:321-378`）输出 8 键，含 `grid_rows`/`fg_rows`；`test_meta_roundtrip`（tests:236）、`test_mask_keeps_foreground_with_blank_glyph`（tests:221） | 否 |
| 11 | 侧车还需 `origin` / `size` / `code_spans` / `skeleton.lines` / `expected_stdout` / `source_sha256` | PM:16（§0 决议 3）、PM:95、narrative:231 | **已修复**（补 `size`） | 修复后侧车 9 键，含 `size: [cols, rows]`（`test_meta_has_size_key_and_roundtrips`）；修复前只有 `schema_version/cols/rows/max_w/grid_rows/fg_rows/fg_count/density`；`origin` 支持可选参数（`grid.py:366-372`）但**不自动填**；**`size` 键完全没有**（只有 cols/rows）；其余键属 C/D/E | 部分：B 补 `size`，其余对齐 A |
| 12 | "D3 前交 3 组固定样例（cat 72×36、logo、slogan）与尺寸/密度表" | PM:201（§9 B②） | 已满足 | `samples/README.md:17-26`（6 行真实数字）；`samples/make_samples.py` 生成 6 网格 + 6 侧车，连跑两遍 sha256 全同 | 否 |
| 13 | "D8 前保证演示用 cat 固定不变，D12 提供第二、三组保形验收图案" | PM:201（§9 B③）；PM:23 | 已满足 | `test_cat_fixture_numbers_are_stable`（tests:283，锁 72×36/1126）；`samples/logo.png` + `slogan.txt` 作为第二、三组 | 否 |
| 14 | "行列 0 基、1 格=1 字符、只可打印 ASCII、禁 Tab/CRLF/全角、图案行不 rstrip" | PM:96；narrative:284 | 部分满足 | charset 侧已强制（`grid.py:69-101`）；**slogan 输入侧未约束**（CJK 见 #15）；行不 rstrip 成立（`types.py:55-59` 直接拼字符） | 是（P1：定 slogan 口径） |
| 15 | Slogan 文本分支稳定（非 ASCII / 超长 / 空）——文档未单列，B 自述"长口号自动折成多行"（`README.md:44-45`） | `ascii-art-executable_B/README.md:43-45` | **已修复** | 修复后：79 字 @72 → 70×20/fg=304（@48 → 48×43/fg=342）、300 字与中文/emoji/Tab 全部 `ValueError`；修复前：空文本 → `ValueError`（tests:129）；`"中文"` @72 → 52×14、`d=0.077`，字形是两排 `@@@@` 方块（字体无 CJK → .notdef）；`"HELLO "*8`（48 字符）→ **72×2、fg=0**；长度 ≥256 → **`OSError [Errno 63]`**（`grid.py:138`） | **是（P0/P1）** |
| 16 | 支持 PNG / JPG | docx §五（一）B 段（"PNG/JPG…"）、`README.md:39` | 已满足（功能层） | 实测 L/RGB/RGBA/P/1 五种模式 + PNG/JPG 都出 `24×6 / fg=38`；`I;16` 也能跑（fg=48，16 位饱和后阈值行为不同）；**但测试只用 L PNG**，无 JPG/RGBA 用例 | 是（P1：补测试） |
| 17 | 透明背景如何定义 | 文档未定义 | 缺失（未定义） | RGBA 透明底 + 白图形 → fg=102（alpha 被忽略、等效黑底）；透明底 + **黑**图形 → `fg=0`（图案整体消失） | 是（P1：定语义+测试） |
| 18 | 分辨率上限语义：宽不超 `max_w`，还是宽高都不超？ | docx 表 2 B 行"尺寸受控"；PM:96 | 部分满足 | 代码只限宽：`grid.py:165` `tw=min(g.width,max_w)`；高度由 `th=round(tw*h/w/cell_aspect)`（`:166`）推导，无上限。文档只写"尺寸受控/宽度不超过约束"（`README.md:40`），**没写高度** | 是（P1：文档明确 + 可选 `max_h`） |
| 19 | `demo/` 放图案、演示脚本 | docx §七；PM:145（目录约定） | 已满足 | `demo/cat.png`（560×560 L，4192 B）；生成脚本 `scripts/demo_grid.py` | 否 |
| 20 | `scripts/demo_grid.py` 会覆写 `demo/cat.png` | 已知隐患（本轮核查） | 部分满足（今天无害） | `scripts/demo_grid.py:84` `make_cat(out / "cat.png")` → `make_cat` 内 `im.save(path)`（`:76`）；实测重生成 sha256 `39e91a4f…` 与现有 `demo/cat.png` **完全一致**，所以现在覆写不变；但绘图代码一改就会静默改 golden | 是（P1：`--out` / 存在即跳过） |
| 21 | README 应覆盖：接口说明、样例表、依赖版本、运行方式 | docx §五（一）A（README 归属 A）+ B 自述契约 | **已修复**（README 重写） | 修复后 README 覆盖新 API、侧车 9 键、样例表、解释器坑，删掉 `CanvasPlan`；修复前：`README.md:36-47` 有接口/参数/运行方式；**缺** `export_meta/load_meta/validate_charset/fg_rows`（`grid.py:321-426`）、缺样例表、缺 Pillow 版本；`README.md:51` 仍写 `CanvasPlan` 参与冻结（PM:14 已决议删除）；`README.md:22-32` 的 venv 指引与 PM:143 冲突 | 是（P1：更新 README） |
| 22 | v2 "PNG 一键转字符画体验也由其负责" | docx §五（一）B 末句 | 缺失 | 只有 `scripts/demo_grid.py`（写死画猫），没有接受任意 PNG 的入口/CLI | 是（P2） |
| 23 | CLI 子命令 `build/verify/detect` | docx §二（一）；PM:203-205（E 负责） | 无需 B 负责 | B 无 `cli.py`，符合分工；`samples/make_samples.py` 只是离线脚本 | 否 |
| 24 | 大图/性能限制 | 文档未写（PM:96 只约束骨架运行 <2s） | 缺失（未定义） | 实测 cat@72 0.011s、slogan@72 0.003s；无 `max_h`/`max_pixels`，50×2000 图产出 1000 行 | 是（P2：写限制） |
| 25 | F 侧消费契约：`PixelGrid` 行主序、单字符、可打印 ASCII、**前景以 `cell.fg` 为准** | `BF/F_对接说明.md:32-34`；`BF/ascii_art_executable/shapecheck.py:21-31,47-48` | 已满足 | `types.py:68-88`（`grid_rows`/`fg_rows`/`fg_mask`）；`test_mask_keeps_foreground_with_blank_glyph`（tests:221）证明 `fg=True, ch=" "` 时掩码仍正确 | 否 |
| 26 | B 与 BF 的 `PixelGrid` 一致（F 已按 BF 版消费） | `BF/F_对接说明.md:38`（F 只新增报告、未改 PixelGrid） | **已修复**（结构化鸭子类型；A 仍须合并字段） | 修复后 `export_meta` 接受 6 字段等价对象（`test_export_meta_accepts_six_field_grid`），缺属性时报具体名字（`test_export_meta_reports_missing_attributes`）；修复前：B: `[width,height,cells,charset,source,threshold,max_w]`（7 字段）vs BF: 同 6 字段无 `max_w`；BF 多 `ShapeReport/DetectionReport`；`export_meta(bf.PixelGrid(...))` → `ValueError: grid must be a PixelGrid, got PixelGrid`（`grid.py:348` 的 isinstance） | **是（P0：与 A 合并）** |
| 27 | 包布局迁入 `ascii_art_executable/shared/`，旧路径留 shim，"保 B 的 13 条测试" | PM:142 | 无需 B 负责（A 执行） | 当前仍是顶层 `shared/`；迁移后 B 的 `from shared.types import ...` 需同步改 | 否（B 配合验证） |
| 28 | 工程基线：D2 前 `git init`、D3–5 `pyproject.toml` | PM:141、PM:5 | 缺失（A/E） | B 目录无 `.git`、无 `pyproject.toml`、无 `LICENSE`（实测 `ls` 均不存在） | 否（B 不负责，但影响上传） |

---

## 三、按优先级的待办

### P0（D3 接口冻结前必须完成）

1. **`max_w` 默认值改 72**
   - 改：`ascii_art_executable/grid.py:123` → `max_w: int = 72`；`README.md:40` 补"默认 72"。
   - 测试：`test_default_max_w_is_72`——`build_grid(demo/cat.png)` 断言 `(width, height) == (72, 36)` 且 `grid.max_w == 72`、`export_meta(grid)["max_w"] == 72`。
   - 依据：PM:201「`max_w` 默认 72」、PM:23「72×36 是 D8 gate 的固定输入」。

2. **`PixelGrid` 合并 + `export_meta` 放宽类型判定**
   - 与 A 合并：把 B 的 `max_w`、`grid_rows`、`fg_rows`、`fg_mask`（`shared/types.py:54,68,73,85`）并进 A 冻结的那份 `types.py`，同时保留 F 的 `ShapeReport`/`DetectionReport`（BF 版）。
   - 改：`grid.py:348` 的 `isinstance(grid, PixelGrid)` 改为结构判定（检查 `width/height/cells/charset` 属性存在），避免跨包/跨版本实例被拒。
   - 测试：`test_export_meta_accepts_structural_grid`（自造同名属性的 dataclass 传入，断言可导出）；`test_types_has_pixelgrid_extras`（防合并时丢字段）。
   - 依据：PM:131/154（G1 要求 types.py 可 import 且三后端 mock 调用不报错）、`BF/F_对接说明.md:38`。

3. **侧车键名对齐 A 的 schema**
   - 改：`export_meta`（`grid.py:350-359`）补 `"size": [cols, rows]`；`origin` 保持可选参数，由 C/D 传；文档里写清"B 只负责网格四件套"。
   - 测试：`test_meta_has_size_key`。
   - 依据：PM:16 侧车字段表（`origin`/`size`/…）、PM:95。

### P1（D8 端到端前）

4. **长口号退化**：`_render_slogan_fit`（`grid.py:264-275`）按 `max_w` 裁剪/缩字号，`_render_slogan`（`:196-214`）兜底不要退回到"图比 max_w 还宽"的路径。
   测试：`test_long_slogan_keeps_foreground`（48/72 字符两档，断言 `height > 1 and fg_count > 0`）。
5. **≥256 字符文本 OSError**：`grid.py:138` 的 `path.is_file()` 包 `try/except OSError`，落到文本分支。
   测试：`test_text_over_255_chars_is_treated_as_text`。
6. **非 ASCII 口号口径**：文档没规定；建议二选一并写进 README/`build_grid` docstring：①仅支持字体覆盖字符；②检测 `.notdef`（实心方块）抛 `ValueError`。
   测试：`test_cjk_slogan_policy`（按选定口径断言）。
7. **透明 PNG 语义**：`grid.py:139` `.convert("L")` 前先 `alpha_composite` 到黑底（与 cat/logo 同为白字黑底），或加 `bg=` 参数。
   测试：`test_transparent_png_black_art`、`test_transparent_png_white_art`。
8. **补格式/模式测试**：`test_jpeg_input`、`test_rgba_input`、`test_palette_png`（现测试只造 L PNG）。
9. **高度上限**：加 `max_h: int | None = 64`（或 `max_cells`），在 `_grid_from_image`（`grid.py:165-166`）生效；测试 `test_tall_image_height_capped`（50×2000@72 断言 `height <= 64`）。
10. **README 更新**：补新 API、样例表（照抄 `samples/README.md:17-26`）、Pillow 版本、`max_w` 默认值；删 `README.md:51` 的 `CanvasPlan`；把 `README.md:22-32` 改为"任意能 import PIL 的解释器 + 已知 dyld 坑"。
11. **demo_grid 覆写**：`scripts/demo_grid.py:84` 改成 `--out` 或 `if not png.exists()`；加 `test_make_cat_matches_golden`（`make_cat(tmp)` 与 `demo/cat.png` 比对 sha256，今天实测一致）。

### P2（可选 / 非 v1 阻塞）

12. **v2「PNG 一键转」**：新增 `scripts/ascii_preview.py <png> [--max-w 72] [--charset]`，或等 E 的 CLI 挂 `preview` 子命令（docx §五（一）B 末句）。
13. **`.gitignore` 补 `.DS_Store`**，并删除 `ascii-art-executable_B/.DS_Store`。
14. **性能/大图限制写进 README**：cat@72 约 11 ms；建议记录"单图 ≤ 4K 边长、建议 max_w ≤ 120"。
15. **包迁移验证**：`shared/` 迁入 `ascii_art_executable/shared/` 后重跑 26 条测试 + `import ascii_art_executable`。

---

## 四、GitHub 上传体检（只检查，未执行任何 git 命令）

### 4.1 现状

| 项 | 结果 |
|---|---|
| 是否 git 仓库 | **否**：`ls -d ascii-art-executable_B/.git` → `No such file or directory`；0 commit |
| `.gitignore` 内容 | `.venv/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`（4 行，41 B） |
| 覆盖情况 | ✅ `.venv` / `__pycache__` / `*.pyc` / `.pytest_cache`；❌ **`.DS_Store` 未覆盖**；❌ `dist/`、`*.egg-info/` 未覆盖（将来打包会漏） |
| 不该上传的体积 | `.venv` **40 M**；`.pytest_cache` 16 K；`__pycache__` 4 处共 **232 K**（tests 152 K / ascii_art_executable 44 K / shared 28 K / scripts 8 K）；`ascii-art-executable_B/.DS_Store` **6148 B**；根目录 `.DS_Store` 10244 B |

### 4.2 按现有 `.gitignore` 过滤后"实际会进仓库"的文件（10 个，50,890 B ≈ 50 KB）

```
   6148  ./.DS_Store            ← 应排除（.gitignore 漏了）
     41  ./.gitignore
   2489  ./README.md
    605  ./ascii_art_executable/__init__.py
  16894  ./ascii_art_executable/grid.py
   4192  ./demo/cat.png
   3675  ./scripts/demo_grid.py
    333  ./shared/__init__.py
   5720  ./shared/types.py
  10793  ./tests/test_grid.py
```

剔除 `.DS_Store` 后是 **9 个文件 / 44,742 B**，干净可传。

### 4.3 上传建议（只写方案，未执行）

- **仓库根**：建议取 `group project`（而不是只把 B 单独开仓）。理由：PM 文档、`samples/`、B 三者要一起被评审；单独开 B 仓库会让 `samples/README.md` 里 `../ascii-art-executable_B/demo/cat.png` 的相对路径和样例表失效。
- **`samples/` 要不要进**：**要**。16 个文件 / 76 K，都是小 PNG + 纯文本，F/C 的联调与 golden 都依赖它；且 `make_samples.py` 幂等（两遍 sha256 全同），适合当 fixtures。
- **`ascii-art-executable_BF/`**：建议**不进**或放 `docs/reference/BF/` 并注明"参考实现、不参与构建"。直接并列进根会让人分不清哪个是可发布版本。
- **目录命名**：`ascii-art-executable_B/` 推荐改名为 `ascii-art-executable/`（与 PM:141 的包名一致）；若不改，`pyproject.toml` 里 `packages = ["ascii_art_executable", "shared"]` 要指对。
- **需要补的文件**：`LICENSE`（课程项目建议 MIT）、`.gitattributes`（`* text=auto`、`*.png binary`、`*.txt text eol=lf`、`*.meta.json text eol=lf`）、顶层 `README.md`（项目简介 + 三命令 + 环境要求）、`pyproject.toml`（A/E，PM:141）、顶层 `.gitignore`（合并 B 的 + `.DS_Store` + `dist/` + `*.egg-info/`）。
- **推荐步骤**（本次未执行）：
  1. 在 `group project` 下 `git init`；
  2. 先写顶层 `.gitignore`（含 `.DS_Store`、`.venv/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`、`dist/`）；
  3. `git add .gitignore README.md ascii-art-executable_B samples/ project-issues-for-PM.md project_issues_narrative.md`（显式白名单，避免 `git add .` 误收 `.venv`）；
  4. `git status --porcelain` 复核**不应出现** `.venv/`、`__pycache__/`、`.DS_Store`；可用 `git check-ignore -v ascii-art-executable_B/.venv` 验证；
  5. 首次 commit → 建远端 → push；D8/D12/D15 各打 tag（PM:140）。

---

## 五、给 PM 的一句话汇报（草稿）

> B 侧功能已闭环：`build_grid` + 单宽字符集校验 + `fg_rows` 掩码 + 侧车导出/回读 + 3 组固定样例，26 条测试全绿、可脱离 pytest 单独跑，G1 判据能过。还差三处会卡 D8：① `max_w` 默认仍是 80（应 72）；② 长口号 ≳48 字退化成空网格、≥256 字直接 `OSError`；③ B 的 `PixelGrid` 多 `max_w`、BF 多两个 F 报告结构，A 必须先合并一份，否则 `export_meta` 跨包即报错。仓库尚未 `git init`，`.gitignore` 漏 `.DS_Store`。

---

## 六、修复前后对照（2026-11-04）

| 项 | 修复前 | 修复后 | 证据 |
|---|---|---|---|
| `max_w` 默认值 | `= 80`，不传参得 80 宽 | `= 72`，不传参 cat → 72×36 / fg=1126 / d=0.4344 | `grid.py` 签名；`test_default_max_w_is_72` |
| 79 字长句 | `72×2`、`fg=0`（空网格；48 宽更只剩 `48×1`） | `70×20`、`fg=304`、d=0.217（48 宽 → `48×43`、`fg=342`） | `test_slogan_79_chars_does_not_degenerate` |
| 300 字文本 | `OSError [Errno 63] File name too long` | `ValueError: slogan text is too long (300 chars > MAX_TEXT_CHARS=200)` | `test_slogan_over_max_chars_raises_value_error` |
| 中文 / emoji / Tab | 渲染成两排实心方块 | `ValueError`，带 `slogan[i]` 与 `U+4E2D` / `U+1F41F` / `U+0009` | `test_slogan_rejects_non_ascii` |
| `export_meta` 类型检查 | `isinstance(grid, PixelGrid)`，喂 BF 版实例报 “got PixelGrid” | 结构化校验 `width/height/cells/charset` + 每格 `fg/level/ch`，缺什么报什么；`max_w` 用 `getattr(..., None)` | `test_export_meta_accepts_six_field_grid`、`..._reports_missing_attributes` |
| 侧车键 | 8 键，无 `size` | 9 键，含 `size: [cols, rows]`；`load_meta` 校验 `size` 与 `cols/rows` 一致，旧侧车缺键自动补 | `test_meta_has_size_key_and_roundtrips`、`test_load_meta_upgrades_legacy_sidecar`、`test_meta_rejects_size_mismatch` |
| `.gitignore` | 4 行，无 `.DS_Store` | 6 行，含 `.DS_Store` 与 `**/.DS_Store`；`git check-ignore -v .DS_Store` → 命中第 6 行 | 临时仓库实测 |
| 测试 | 26 条 | **38 条全绿**（新增 12 条） | `pytest -q` → `38 passed in 0.19s` |
| 样例数字 | cat 72×36/1126/0.4344 | **完全不变**（6 组数字逐项一致，重跑幂等） | `samples/make_samples.py` 输出 |

修复涉及文件：`ascii_art_executable/grid.py`、`tests/test_grid.py`、`README.md`、`.gitignore`、`samples/*.meta.json`、`samples/README.md`。
