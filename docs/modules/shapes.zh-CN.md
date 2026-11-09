# B 模块（v2）—— 图案生成 `codeart/shapes.py`

[English](shapes.md)

B 不再做图片降采样，而是**生成图案**：给定图案请求，返回一个 `Mask`——排版引擎（C）可填的
格子集合，以及校验器（F）要度量的几何特征。B 不产出任何源码。

## 接口

```python
from codeart import FontMetrics, ShapeSpec, SizeRequest, build_mask, geometry_metrics

mask = build_mask(
    ShapeSpec(kind="cat"),          # "circle" | "cat" | "code"
    SizeRequest(height_rows=32),    # 行数由 C 决定
    FontMetrics(cell_aspect=0.5),   # 项目固定常数
)
```

`build_mask(shape_spec, size_request, font_metrics, *, ctx=None) -> Mask`

| 类型 | 字段 |
|---|---|
| `FontMetrics` | `cell_aspect: float = 0.5`（字符宽 / 字符高，单位 px） |
| `SizeRequest` | `height_rows: int` |
| `ShapeSpec` | `kind: str`、`text: str \| None`、`font_id: str \| None`、`inner_radius: float \| None` |
| `Mask` | `kind`、`width`、`height`、`allowed[row][col]`、`spans[row]`、`scale`、`font_metrics`、`features`、`inner_radius` |

`ctx` 是可选的取消上下文：若提供且带 `raise_if_cancelled()` 或 `check()`，每生成一行调用一次
（鸭子类型，不硬依赖 F 的 `contracts.py`）。

### 尺寸

行数由 C 决定，B 按物理宽高比 `r` 反推列数：

```
columns = ceil(height_rows × r / cell_aspect)
```

`cell_aspect = 0.5` 时，`r = 1.0` 的图案在 32 行下是 64 列（物理宽 `64 × 0.5 = 32`，与高相等）。
`scale = height_rows / 2` 表示"每个图案单位占多少行"（图案归一化到 `v ∈ [-1, 1]`）。

| 图案 | r | 32 行 | 64 行 |
|---|---|---|---|
| `circle` | 1.0 | 64×32 | 128×64 |
| `cat` | 1.0 | 64×32 | 128×64 |
| `code` | 25/9 ≈ 2.778 | 178×32 | 356×64 |

## 三种图案

### `circle`

实心圆：格中心满足 `u² + v² ≤ 1` 即可填；`(u, v)` 为归一化坐标，`v ∈ [-1, 1]`，`u` 按
`cell_aspect` 缩放。外接矩形正好是请求的矩形，物理宽高比恒为 1.0。

### `cat`

猫头：椭圆头（`rx = 0.95`、`ry = 0.80`，中心略偏下）+ 两个三角形耳朵（耳尖顶到上边界）+
两个椭圆眼洞 + 一个鼻洞。孔洞是从实心轮廓中挖出来的，因此头部仍是一个连通的可填区域、内部有 3 个孔。

### `code`

实心矩形中挖空 **CODE** 四个字母，使用内置 5×7 点阵字形（字距 1 单位、四周留 1 单位边距，
保证笔画不贴边）。`text` 默认 `"CODE"`，传其它值抛 `INVALID_SHAPE`。字形表在
`codeart/shapes.py` 的 `_GLYPHS`，就是普通 ASCII 画，方便修改。

## `spans` 约定

`spans[row]` 是该行所有可填区间，用半开区间 `(start, end)`：

- 按 `start` 有序、互不重叠、`0 ≤ start < end ≤ width`；
- 孔洞会把一行切成多段（`cat` 与 `code` 都有多区间行，例如穿过猫眼的那几行）；
- 整行可填是 `((0, width),)`；整行不可填是 `()`。

用 spans 重建出来的行必须与 `allowed[row]` 完全一致；测试在 32/64 行下对三种图案都做了断言。

`tests/fixtures/shapes/{circle,cat,code}_32.json` 是 32 行下 `allowed` + `spans` 的固定快照
（合计约 12 KB），回归测试会逐行比对。

## `features`

命名几何，每项是 0 基 `(row, col)` 的集合：

| 键 | 含义 |
|---|---|
| `eye_left`、`eye_right` | 两个眼洞（这些格 `allowed == False`） |
| `nose` | 鼻洞 |
| `ear_left`、`ear_right` | 两只耳朵的轮廓（可填格） |
| `eyes`、`ears` | 左右两侧的并集 |
| `code_strokes` | `code` 矩形里被挖空的笔画格 |

圆没有 features（`{}`）。眼、鼻描述的是孔洞，所以它们的格子一定不可填。

## `geometry_metrics(mask)`

给校验器（E）用的度量，返回：

```
kind, cols, rows, cell_aspect,
bbox: {cols, rows, ratio},                 # ratio = cols*cell_aspect/rows
allowed_cells, spans_total, rows_with_multiple_spans,
eye_cells: {left, right}, nose_cells,
ear_gap_rows,                             # 两个耳尖之间的凹陷行数
holes: [{cells, centroid: {row, col}}],   # 只统计内部孔洞
code_stroke_cells
```

## 供验收使用的放大参考数据

`tests/fixtures/shapes/metrics_h{32,64,96,128}.json` 是给 E 用的生成快照：每个文件覆盖
`circle`、`cat` 与 `code`（`text="CODE"`）三种图案在同一高度下的几何数据。重新生成：

```bash
python scripts/gen_shape_metrics.py
```

`h128` 是 E 验收高度集（h32/h64/h128）所用的高度；`h96` 为了保持连续性而保留。

脚本对每个「图案 × 高度」调用 `build_mask` + `geometry_metrics`，没有手填数字；输出确定
（两次运行字节一致），`tests/test_shape_metrics.py` 会校验 fixture 与当前实现一致。

顶层字段：

| 字段 | 含义 |
|---|---|
| `schema_version` | `1` |
| `cell_aspect` | `0.5`，项目固定的字符宽 / 字符高 |
| `height_rows` | 本文件所有图案共用的行数 |
| `generated_by` | 生成脚本路径 `scripts/gen_shape_metrics.py` |
| `tolerance` | E 使用的容差（见下） |
| `shapes` | `circle`、`cat`、`code` → 各图案的记录 |
| `scaling_expectation` | 文字说明 + 缩放公式的参考高度（`32`） |

单个图案的记录：

| 字段 | 含义 |
|---|---|
| `cols`、`rows` | mask 尺寸（列数由图案物理宽高比决定） |
| `bbox_ratio` | 占据的外接矩形比：`bbox_cols * cell_aspect / bbox_rows` |
| `allowed_cells` | 可填格数 |
| `spans_total` | 所有行上极大可填区间的总数 |
| `rows_with_multiple_spans` | 被至少一个孔洞切成多段的行数 |
| `features` | 只含命名的眼/鼻洞；`circle` 与 `code` 为 `{}` |
| `hole_count` | 命名孔洞特征数：`cat` 为 `3`，其余为 `0` |
| `ear_gap_rows` | 仅 `cat`：两个耳尖之间的凹陷行数；其余为 `null` |

每个 feature：

| 字段 | 含义 |
|---|---|
| `cells` | 该特征的格数（即下文的 `A_ref`） |
| `bbox` | 闭区间 `[min_row, min_col, max_row, max_col]` |
| `centroid` | `[row, col]`，采用**格中心**坐标（下标 + 0.5） |

### 容差口径

对 32 行下测得面积为 `A_ref` 的 feature：

```
A_expected(h) = A_ref * (h / 32) ** 2
area_limit(h) = max(area_rel * A_expected(h),
                    area_perimeter_factor * sqrt(A_expected(h)),
                    area_min_cells)
area_ok      = abs(cells(h) - A_expected(h)) <= area_limit(h)
centroid_ok  = abs(centroid(h)[axis] - centroid(32)[axis] * h / 32) <= centroid_abs_cells
```

面积项刻意做成**周长级**：参考格数是在格中心采样的，孔洞实测格数与理想连续面积之差，
来自轮廓切过的那些格，误差与孔洞**周长**成正比；而面积为 `A` 的孔洞，周长约按 `sqrt(A)`
增长，不是常数。所以任何固定的绝对格数都会两头不对：`20` 格让 32 行只有 10 格的鼻子
允许了 300% 误差，而 96 行眼睛本身 16 格的量化漂移就已经吃掉这份预算的 80%，几乎没给
真正的回归留下余量。

以 32 行为参考实测（`area_perimeter_factor = 4.0`、`area_rel = 0.02`、
`area_min_cells = 2`）：

| feature | h | `A_ref` | `A_expected` | 实测 | `area_limit` | 结论 |
|---|---|---|---|---|---|---|
| 眼 | 32 | 43 | 43 | 43 | 26.2 | 通过（参考本身） |
| 眼 | 64 | 43 | 172 | 163 | 52.5 | 通过（漂 9 格） |
| 眼 | 96 | 43 | 387 | 371 | 78.7 | 通过（漂 16 格） |
| 鼻 | 32 | 10 | 10 | 10 | 12.6 | 通过（参考本身） |
| 鼻 | 64 | 10 | 40 | 34 | 25.3 | 通过（漂 6 格） |
| 鼻 | 96 | 10 | 90 | 74 | 37.9 | 通过（漂 16 格） |

系数 4.0 对应格中心采样下圆盘边界环的规模：边界格数大致是 `4 * sqrt(A)`。这样既能容纳
实测漂移、留一点余量，又不会放过参考值错 50% 的实现。面积更大的特征由 2% 相对项主导；
`area_min_cells = 2` 避免退化成 1 格的孔洞拿到零预算。`bbox_ratio` 无量纲，四档之间差异
不得超过 `bbox_ratio_abs = 0.05`。

`centroid` 刻意存成格中心坐标：原始下标带 `-0.5` 偏置，不随 `h` 缩放；`(row + 0.5)` 才会。
`hole_count` 只数命名的眼/鼻孔洞，不等同于 `len(geometry_metrics()["holes"])`——后者在某些
分辨率下会多出 1 格的量化空洞。

### E 的断言示例

```python
doc = json.loads((FIXTURES / "metrics_h32.json").read_text())
ref, tol = doc["shapes"]["cat"]["features"]["eye_left"], doc["tolerance"]
expected = ref["cells"] * (96 / 32) ** 2
limit = max(tol["area_rel"] * expected,
            tol["area_perimeter_factor"] * expected ** 0.5,
            tol["area_min_cells"])
got = len(build_mask(ShapeSpec("cat"), SizeRequest(96), FontMetrics()).features["eye_left"])
assert abs(got - expected) <= limit  # 371 vs 387，limit 78.7
```

`tests/test_shape_metrics.py` 还会检查各档 `features` 键集合一致、面积平方缩放、质心线性缩放、
`bbox_ratio` 与高度无关，以及生成脚本的字节级幂等。另有两个反向测试守住另一边：把参考眼
格数放大 1.5 倍必须被缩放一致性断言拒绝；h96 眼睛少 100 格必须超出 `area_limit`。

## 验收指标（32 行实测）

| 指标 | 要求 | 实测 |
|---|---|---|
| 每只眼格数 | ≥ 4 | 43 / 43 |
| 鼻子格数 | ≥ 2 | 10 |
| 耳峰间凹陷 | ≥ 2 行 | 5 |
| 圆 bbox 比 | 1.0 ± 0.05 | 1.000 |
| 确定性 | 两次调用完全相同 | 是（dataclass 相等） |
| 32 → 64 放大 | 眼面积约 ×4、几何保持 | 43 → 163（×3.79），鼻 10 → 34，凹陷 5 → 10 |

## 错误码

`ShapeError` 继承 `ValueError`，带稳定字段 `code`：

| code | 触发条件 |
|---|---|
| `INVALID_SHAPE` | 未知 `kind`、`text != "CODE"`、`inner_radius` 非 `None`（暂不支持环形） |
| `INVALID_SIZE` | `height_rows` 不是正整数，或 `cell_aspect` 非正 |

## 跑测试

```bash
python -m pytest tests/test_shapes.py -q     # 17 passed
```

覆盖：三种图案在 32/64 行生成、spans 重建一致性、孔洞不可填、多区间行、上面的验收指标、
确定性、错误码、`ctx` 鸭子类型钩子，以及 fixture 回归。
