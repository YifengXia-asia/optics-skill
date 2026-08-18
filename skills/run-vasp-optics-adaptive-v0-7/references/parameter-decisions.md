# 参数和流程决策（v0.7）

## 1. 决策顺序

1. 读取 POSCAR/POTCAR/KPOINTS 和可选 INCAR。
2. 判断周期维度候选，不判断最终金属或带隙。
3. 保留用户有效参数，只给缺失值建议。
4. 运行基态 DFT。
5. 从实际本征值和占据数确定电子类型。
6. 选择体相、非体相或金属光学分支。

材料名称永远不参与分支。

## 2. 结构候选

| 分类 | 线索 | LOPTICS 解释 |
|---|---|---|
| `bulk-3d-candidate` | 三个方向均周期采样，没有明显真空轴 | 可按三维体相介电函数解释 |
| `slab-or-2d-candidate` | 一个长晶格方向且该方向 K 点为 1 | 可运行，但介电函数随真空体积变化 |
| `wire-or-1d-candidate` | 两个相对较长且仅用 Gamma 采样的方向；`classification.vacuum_axis_min_angstrom` 仅是触发复核的下限 | 可运行，但横向真空归一化及真空厚度必须另行收敛 |
| `molecule-or-isolated-candidate` | 三个方向大盒子且 Gamma-only | 三维超胞介电量不是分子内禀光学常数 |

分类只是候选。对非体相，若用户不接受超胞依赖则停止。

## 3. 电子分类

`classify_electronic.py` 使用最后一个 VASP 本征值块：

- 检查部分占据；
- 检查能带是否跨越费米能级；
- 从完全占据态顶和空态底估计带隙；
- 小于等于 `gap_threshold_eV` 时标为 `metal-or-semimetal`；
- 大于等于 `insulator_gap_threshold_eV` 时标为 `insulator`；
- 中间标为 `semiconductor`。

该标签用于工作流路由。严谨带隙仍需合适的 K 点路径、泛函和收敛测试。

## 4. 用户参数优先

当存在输入 INCAR 且策略为 `preserve-user`：

- 保留 `GGA/METAGGA/LDAU*/IVDW/LASPH/LMAXMIX`；
- 保留 `ISPIN/MAGMOM/LSORBIT/LNONCOLLINEAR/SAXIS`；
- 用户 ENCUT、ISMEAR、SIGMA、ISPIN、ALGO、EDIFF 优先于自动建议；
- 若 ENCUT 低于最大 ENMAX、磁性/SOC 设置不完整或与 WAVECAR 不兼容，则停止并说明原因。

运行阶段仍会强制设置完成当前任务所需的 `NSW/IBRION/LWAVE/LCHARG/LOPTICS/ICHARG/ISTART`。

## 5. 起始值

```text
ENCUT_auto = ceil(max(ENMAX) / encut_rounding_eV) × encut_rounding_eV
N_e = Σ(ZVAL_i × count_i)
N_occ ≈ ceil(N_e / 2)
NBANDS_auto = max(nbands_minimum, N_occ + max(nbands_empty_minimum, floor(N_occ × nbands_empty_fraction)))
```

这些起点以及 K 点对照密度均位于 `parameters.heuristics`，可在用户确认后修改；默认值只用于第一轮演示，正式计算必须做收敛测试。

DFT 与 LOPTICS 使用同一个 NBANDS，避免 WAVECAR 中能带数变化警告。VASP 官方建议 LOPTICS 通常需要比默认值多约 2–3 倍空带；所以此公式只是低成本起点，必须围绕目标能量窗口增加 NBANDS 验证。

实际 KPOINTS 始终来自用户文件。几何候选只用于提示是否需要更密网格或真空方向设为 1。

若实际网格严格为 `1×1×1 Gamma`，且用户配置了 `vasp_gamma_bin`，可自动使用 Gamma-only 可执行文件；其他网格必须使用标准版本。该选择来自 KPOINTS，不来自材料名称。

## 6. 电子分支

| 电子类型 | 起始设置 | 额外要求 |
|---|---|---|
| semiconductor/insulator | `ISMEAR=0, SIGMA=0.01, CSHIFT=0.10` | 检查带隙和吸收边收敛 |
| metal-or-semimetal + interband-only | 用户确认的展宽 | 必须声明低频 Drude/带内贡献不完整 |
| metal-or-semimetal + drude | `WPLASMAI>0` | 宽度来自实验或收敛依据，不自动猜值 |

`NEDOS=2000` 只控制频率网格。`SIGMA` 与 `CSHIFT` 都会展宽光谱，避免无意识地同时使用过大的双重展宽。

## 7. 收敛与外部对照

至少比较：

- ENCUT：当前值和更高一级；
- KPOINTS：用户值和更密网格；
- NBANDS：能覆盖目标最高光子能量；
- CSHIFT/SIGMA：峰位应稳定，峰宽变化需说明；
- 非体相：至少两个真空厚度或做正确低维归一化；
- 金属：低频谱对 K 点和 Drude 宽度的依赖。

外部数据只比较同组成、晶相、泛函、近似和温度定义，不能替代本计算收敛。
