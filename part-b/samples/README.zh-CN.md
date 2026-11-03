# 样例资产（B：图案输入与字符画）

[English](README.md)

三组**固定样例**，对应 `project-issues-for-PM.md` §9 B②（"cat 72×36、logo、slogan 与尺寸/密度表"）
和 D8 / D12 两个 gate 的验收输入。所有网格都由 B 的 `build_grid` 真实渲染，**没有一行是手写的**；
每份网格旁的 `.meta.json` 由 `export_meta` 生成（B 的侧车切片）。

## 约定

- 三张图都是**白字黑底**（与 `../demo/cat.png` 一致），`build_grid` 默认 `threshold=128` 下"亮 = 前景"，
  下游**不需要** `invert=True`。若换用黑字白底的图，记得传 `invert=True`。
- 1 格 = 1 个可打印 ASCII 字符；行不做 `rstrip`；坐标 0 基。
- `fg_rows` 里 `1` 的格必须被非空字符占据——注意**不能**用 `grid_rows` 反推掩码：
  前景格可能正好落在 `level 0` 上而显示为空格（`fg=True, ch=" "`）。

## 对照表（脚本真实输出）

| 组别 | 源 | max_w | cols × rows | fg_count | density |
|---|---|---|---|---|---|
| cat | `../demo/cat.png`（560×560 L） | 72 | 72 × 36 | 1126 | 0.4344 |
| cat | 同上 | 48 | 48 × 24 | 525 | 0.4557 |
| logo | `logo.png`（512×512 L，带外框的粗体 A） | 72 | 72 × 36 | 581 | 0.2242 |
| logo | 同上 | 48 | 48 × 24 | 194 | 0.1684 |
| slogan | 文本 `"ASCII"`（`slogan.txt`） | 72 | 72 × 13 | 280 | 0.2991 |
| slogan | 同上 | 48 | 48 × 8 | 128 | 0.3333 |

> density = fg_count / (cols×rows)，例：cat 72 宽 = 1126 / 2592 = 0.434414。

## 生成方式

```bash
python3 samples/make_samples.py     # 重画 logo.png，重渲染 6 份网格 + 6 份侧车，打印上表
```

- 脚本是**幂等**的：纯整数几何 + 确定性 `build_grid`，不含时间戳；连跑两遍所有产物 sha256 完全一致。
- 脚本自己把工程根加进 `sys.path`，从任意目录运行都行；需要能 `import PIL` 的解释器。
- slogan 走文本分支（`_render_slogan` 挑"放得下的最大字号"再折行）；`"ASCII"` 在 72/48 下都是单行，
  所以正好填满宽度上限。
- 换机器时 slogan 的字体可能不同，网格可能变；`verify` / `check_shape` 应信这份快照，**不要**现场重新渲染。

## 文件清单

| 文件 | 说明 |
|---|---|
| `logo.png` | 512×512 灰度图：对称留白 48px、20px 外框、约 39px 笔画的多边形粗体 A（平底直角、PIL 不抗锯齿，边缘像素级锐利） |
| `slogan.txt` | 固定 Slogan：`ASCII`（含换行） |
| `make_samples.py` | 可复现脚本（画图 + 渲染 + 写侧车 + 打表） |
| `grid_{cat,logo,slogan}_{72,48}.txt` | 纯文本网格，每行 cols 个字符，共 rows 行 |
| `grid_{cat,logo,slogan}_{72,48}.meta.json` | 侧车：`schema_version / cols / rows / size / max_w / grid_rows / fg_rows / fg_count / density`（`size` = `[cols, rows]`，B 侧 9 个键） |

## 给下游的接口提醒

- **F（保形）**：直接吃 `PixelGrid`；只有文件时读 `grid_rows` + `fg_rows` 重建掩码。
  `origin` 由排版阶段（C/D）提供，本目录不含。
- **C/D（后端）**：`fg_rows` 为 `1` 的格必须落非空字符；`code_spans` 覆盖的格要记进侧车。
- **E（校验）**：`export_meta` 写出的 9 个键就是 B 负责的那一半侧车，其余键（`origin`/`code_spans`/
  `skeleton.lines`/`expected_stdout`/`source_sha256`）由 C/D/E 补齐。
- 侧车自 v1.1 起多一个 `size: [cols, rows]`；旧侧车缺这个键时 `load_meta` 会自动补，不会报错。

## 尺度提醒（别混抄）

- **BF 演示**用的是 `max_w=48` → `48×24`、`525` 个前景格。
- **PM 文档的 cat 验收**用的是 `max_w=72` → `72×36`、`1126` 个前景格。
- 两者是同一张猫的不同尺度，格子数、密度、保形阈值都不能互相套用。
