# B 部分 — 图像 / 口号 → 字符网格

[English](README.md)

本目录是 *ASCII Art Executable* 项目的 **B 部分**：图案输入模块。它把一张图（PNG/JPG）
或一句口号变成稠密的字符网格（`PixelGrid`）——每格严格对应源码的一列，前景/背景掩码
显式保留，并同时产出一份 JSON 侧车，让下游（代码排版、保形校验）不必重新渲染即可消费。

仓库里所有内容都在 `part-b/` 下，根目录的 `LICENSE` 与 `README.md` 未做任何改动。

## 它做什么

- **降采样**：Pillow 读图 → 灰度 → 网格；宽度受 `max_w` 约束（默认 **72**，即 D8 golden
  尺度：`demo/cat.png` → 72×36）。
- **掩码**：每格带 `fg`（前景 = 必须被占用）、`level`（密度档）、`ch`（字形）。
  `fg=True` 且 `ch=" "` 是合法状态——这也是掩码必须单独导出的原因。
- **字符集校验**：一个字形 = 一个可打印单列 ASCII 字符（`0x20`–`0x7E`）；
  Tab / 全角 / 中文 / emoji 一律 `ValueError`。
- **Alpha**：图片的 alpha 通道确实存在透明像素（任一像素 `alpha < 128`）时，alpha 就是形状掩码——
  透明像素一律背景（不看 RGB 值），所以"透明底 + 黑色 logo"不会再整块消失；不透明像素为前景，
  其密度档位被抬到 ≥ 1，深色图形也能显示字形。完全不透明的 RGBA 仍走亮度阈值。
- **口号**：只接受可打印 ASCII，按 `max_w` 折行，长度上限 `MAX_TEXT_CHARS = 200`；
  空文本 / 超长 / 非 ASCII 都抛 `ValueError`，并指出具体位置（如 `slogan[3] = '中' (U+4E2D)`）。
- **侧车**：`export_meta()` 写 `<out>.meta.json`；`load_meta()` 读回并校验。

## 接口

```python
build_grid(src, charset=" .:-=+*#%@", max_w=72, max_h=None,
           threshold=128.0, invert=False, cell_aspect=2.0) -> PixelGrid
```

| 参数 | 含义 |
|---|---|
| `src` | 图像路径（PNG/JPG 等 Pillow 支持的格式）**或**口号文本；不是已存在文件路径的字符串按文本处理 |
| `charset` | 疏→密字符集，首字符视为空白（默认 `" .:-=+*#%@"`） |
| `max_w` | 宽度上限，正整数，**默认 72** |
| `max_h` | 可选高度上限，正整数或 `None`（**默认 `None`** = 不限）；两个上限同时生效时按更紧的比例缩放，保证宽 ≤ `max_w` 且高 ≤ `max_h` |
| `threshold` | 灰度 0–255 的前/背景阈值（亮 ≥ 阈值 = 前景） |
| `invert` | 反转前/背景（深色主体、浅色背景时用） |
| `cell_aspect` | 终端字符高宽比，默认 2.0 |

`PixelGrid` 提供 `width`、`height`、`cells`、`charset`、`source`、`threshold`、`max_w`，
以及 `at(x, y)`、`row(y)`、`render()`、`grid_rows`、`fg_rows`、`fg_mask()`、`fg_count`、`density`。

## 快速开始

```bash
cd part-b
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests -q          # 45 passed
./.venv/bin/python tests/test_grid.py          # 同一批 45 条，无需 pytest

# 演示：打印猫的字符网格；已存在的 cat.png 默认跳过，--force 才覆盖
./.venv/bin/python scripts/demo_grid.py 72
./.venv/bin/python scripts/demo_grid.py 72 --out /tmp/cat_demo.png --force
```

任意 Python ≥ 3.10 且能 `import PIL` 即可。（macOS 已知坑：从别的机器拷来的 `.venv`
可能卡死在 `import PIL`（dyld 代码签名校验），换系统解释器或重建 venv。）

## 口号规则

- 只接受可打印 ASCII + `\n`；其它一律 `ValueError` 并带位置与码位
  （避免把中文/emoji 渲染成实心 `.notdef` 方块）；
- 超过 `MAX_TEXT_CHARS = 200` → `ValueError`（请写进文件传路径）；
- 按空格折行到 `max_w`；单个超宽单词才硬切；
- 长文本会缩小字号/增高画布，而不是退化成 1 行空网格（79 字在 `max_w=72` 下 → 70×20、fg=304）。

## 侧车（`<out>.meta.json`）

`export_meta(grid, out=None, *, origin=None, extra=None) -> dict`

| 键 | 含义 |
|---|---|
| `schema_version` | 侧车版本（当前 1） |
| `cols` / `rows` / `size` | 列数 / 行数 / `[cols, rows]` |
| `max_w` | 构建时使用的宽度上限（未知时为 `null`） |
| `grid_rows` | 每行字形（背景格是空格） |
| `fg_rows` | 前景掩码，`"1"` = 前景，`"0"` = 背景 |
| `fg_count` / `density` | 前景格数 / 前景占比 |

两种行都要存：前景格落在 `level 0` 时字形就是空格，`grid_rows` 里与背景无法区分，
掩码只能来自 `fg_rows`（或 `cell.fg`），**不要**用 `render()` 反推。

`load_meta()` 会校验一致性，并兼容旧侧车（缺 `max_w` → `null`，缺 `size` → `[cols, rows]`）。

## 与 6 字段 `PixelGrid` 的兼容性

B 的 `PixelGrid` 是 6 字段版的**超集**：`max_w` 是唯一多出来的字段，且位于末尾、默认 `None`，
所以 5/6 个位置参数的旧构造方式仍然可用。`export_meta()` 采用**结构化（鸭子类型）**校验——
只要求 `width`、`height`、`cells`、`charset`，每格有 `fg` / `level` / `ch`——因此 6 字段对象
同样可用，`max_w` 用 `getattr(grid, "max_w", None)` 读取；缺字段会按名字报错。

## 样例

`part-b/samples/` 里有三组固定样例，各出 `max_w=72` 与 `48` 两份
（重跑：`python3 samples/make_samples.py`，幂等）：

| 组别 | 源 | max_w | cols × rows | fg_count | density |
|---|---|---|---|---|---|
| cat | `demo/cat.png`（560×560 L） | 72 | 72 × 36 | 1126 | 0.4344 |
| cat | 同上 | 48 | 48 × 24 | 525 | 0.4557 |
| logo | `samples/logo.png`（512×512 L） | 72 | 72 × 36 | 581 | 0.2242 |
| logo | 同上 | 48 | 48 × 24 | 194 | 0.1684 |
| slogan | 文本 `"ASCII"` | 72 | 72 × 13 | 280 | 0.2991 |
| slogan | 同上 | 48 | 48 × 8 | 128 | 0.3333 |

每份网格都有同名 `.meta.json` 侧车；`samples/README.zh-CN.md` 说明约定
（白字黑底、origin 由排版阶段提供）。

## 测试

45 条全部通过（`pytest -q tests`）：

```
45 passed in 0.48s
```

覆盖：图像路径（宽/高上限、前后景标记、反色、字符高宽比）、PNG/JPG/RGBA/调色板输入、
alpha 作掩码（透明底 + 黑方块）、字符集校验（可打印 ASCII、Tab/中文/emoji 拒绝、去重）、
掩码导出（`fg=True` 但字形为空）、侧车往返、鸭子类型导出，以及口号契约（短文本、79 字、
300 字、空白、中文/emoji/Tab、超长单词硬切）。
