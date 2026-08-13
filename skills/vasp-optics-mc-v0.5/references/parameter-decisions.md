# 参数决策说明（v0.4）

## 目录

1. 输入事实
2. 体系分类
3. 起始参数公式
4. 人工确认闸门
5. 收敛与适用边界

## 1. 输入事实

只把文件中的事实当作事实：

- POSCAR：元素顺序、原子数、晶格向量和晶胞尺度；
- POTCAR：每个元素块的 `TITEL`、`ENMAX`、`ZVAL`；
- KPOINTS：显式网格、Gamma/Monkhorst 模式和偏移。

材料名称不参与分类。`material` 和 `prefix` 只影响显示或文件名。

## 2. 体系分类

`config_loader.py` 先判断结构，再判断电子性质：

| 输出 | 触发线索 | 意义 |
|---|---|---|
| `bulk-3d-candidate` | 三个晶格长度相近，网格没有明显真空方向 | 可按三维周期体系给起始网格 |
| `slab-or-2d-candidate` | 最大晶格长度显著更长，或该方向 K 点为 1 | 需要确认真空层和介电归一化 |
| `molecule-or-isolated-candidate` | 大晶胞且 Gamma-only | 不要直接套用体相介电函数解释 |
| `unknown-needs-dft-check` | `system_hint=auto` 且没有用户电子性质 | POSCAR/POTCAR/KPOINTS 不能证明带隙或金属性 |

含过渡金属、稀土或锕系元素只产生“磁性候选”提醒；重元素只产生“SOC 需决定”提醒。它们不是自动物理结论。

## 3. 起始参数公式

### ENCUT

```text
max_enmax = max(POTCAR 每个元素块的 ENMAX)
encut_auto = ceil(max_enmax / 10 eV) × 10 eV
```

这只是起点。定量峰位前至少比较相邻 ENCUT，并记录使用的 POTCAR 家族。

### KPOINTS

对三维候选体系，以中等晶格长度 `a_ref` 和密度因子 `d=6`（用户提示金属时 `d=8`）估算：

```text
n_i = max(1, ceil(d × a_ref / |a_i|))
```

对疑似二维/表面体系，将最长、疑似真空方向设为 1；对分子/孤立体系给出 Gamma-only 候选。脚本只建议，不会覆盖用户输入的 KPOINTS。

### NBANDS

```text
N_e = Σ(ZVAL_i × count_i)
N_occ ≈ ceil(N_e / 2)
NBANDS_auto = max(32, N_occ + max(16, floor(N_occ/2)))
```

该式没有知道目标光子能量，因此只能作为起点。提高目标能量时增加空带，并检查高能介电函数是否随 NBANDS 稳定。

### 展宽、自旋与响应

- 非金属提示：`ISMEAR=0`、`SIGMA=0.01`、`CSHIFT=0.10` 为起始值；
- 用户提示金属：给出 `ISMEAR=1`、较大 `SIGMA/CSHIFT` 的候选值，并要求单独确认金属光学方案；
- 磁性候选：给 `ISPIN=2` 建议，要求初始磁矩和磁态收敛证据；
- 响应默认 `density-density`，不能把 `current-current` 数据混作同一列。

## 4. 人工确认闸门

`prepare.py` 必须看到：

```yaml
run:
  confirm_recommendations: true
```

确认前要回答：

1. 结构类别和三维介电张量解释是否适合？
2. 电子性质是否已有 DFT 证据，还是仍为未知？
3. ENCUT、KPOINTS、NBANDS 是否覆盖目标能量？
4. 磁性、SOC、真空层和展宽是否需要额外方案？

## 5. 收敛与适用边界

至少对 ENCUT、KPOINTS、NBANDS、CSHIFT 做相邻值比较。记录泛函、POTCAR 日期/家族、晶相、温度和目标能量。外部文献只能作为同体系合理性检查，不能替代本计算收敛和实验定义。
