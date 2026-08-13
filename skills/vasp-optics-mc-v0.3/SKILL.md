---
name: vasp-optics-mc-v0-3
description: "Use when the user wants a material-aware VASP independent-particle optical workflow: validate POSCAR/POTCAR/KPOINTS, classify Si, SiC, GaAs, or an unknown material, choose and explain starting parameters, run DFT then LOPTICS, extract epsilon1/epsilon2/n/k/alpha/reflectivity, and validate energy- and wavelength-domain outputs. Do not use for GW, BSE, CHI/RPA, local-field, phonon/ionic dielectric, SOC, spin/magnetic, metallic, or structural-relaxation workflows."
---

# VASP 材料适配型独立粒子光学流程 v0.3

## Overview

本 Skill 将以下流程封装为可检查、可执行、可验证的步骤：

`POSCAR/POTCAR/KPOINTS → DFT → WAVECAR/CHGCAR → LOPTICS → vasprun.xml → epsilon1/epsilon2 → n/k/alpha/R → 能量域和波长域 CSV/PNG → 验证`

第一版材料 profile 采用 VASP 常见示例：Si、SiC、GaAs。SiC profile
复现已经跑通的 demo：`ENCUT=414`、`6×6×6 Gamma`、`NBANDS=64`、
`CSHIFT=0.100`、`NEDOS=2000`。这些是起始建议，不是所有材料的硬编码常量。

v0.3 允许用户更换材料、前缀、POTCAR、ENCUT、NBANDS、KPOINTS、MPI 资源和路径。
未知材料使用通用检查，并要求用户说明参数选择和收敛测试计划。

## When to Use

当用户需要对非金属或绝缘材料执行“基态 DFT → VASP LOPTICS → 光学后处理”时使用。
输出包括：

- `epsilon1`：介电函数实部；
- `epsilon2`：介电函数虚部；
- `n`：折射率；
- `k`：消光系数；
- `alpha`：吸收系数，单位 `cm^-1`；
- `R`：正入射反射率。

不适用于 GW、BSE、`ALGO=CHI`、RPA/局域场、声子或离子介电响应、SOC、
自旋/磁性、金属、结构优化或通用高通量路由。遇到这些请求时停止当前流程，
提出单独的计算 profile。

## Prerequisites

1. 可执行的 `vasp_std`、MPI 启动器，以及必要时的 oneAPI 环境脚本。
2. 安装 PyYAML、NumPy、pandas、matplotlib、lxml 的后处理 Python 环境。
3. 新输入目录中有 `POSCAR`、`POTCAR`、`KPOINTS`。
4. POTCAR 的元素块顺序必须和 POSCAR 一致。程序读取 `TITEL`、`ENMAX`、`ZVAL`。
5. KPOINTS 必须是 Gamma-centered，并与配置的网格和偏移一致。
6. 输出目录必须是新目录，不能覆盖已有 VASP 结果。
7. `run.profile` 可设置为 `auto`、`Si`、`SiC`、`GaAs` 或 `generic`。

先检查输入：

```bash
python <skill-path>/scripts/config_loader.py --config config.yaml --check
```

检查失败时，先修复程序报告的 POSCAR/POTCAR/KPOINTS 问题，不要直接运行 VASP。

## Configuration and parameter policy

复制 `config.yaml.example` 为 `config.yaml`。更换材料时至少修改：

```yaml
run:
  material: <材料名>
  prefix: <输出前缀>
  expected_elements: [<按 POSCAR/POTCAR 顺序填写>]
  profile: auto
```

`prefix` 只控制 CSV/PNG 文件名，不改变物理计算。

### 三个起始 profile

| Profile | 元素顺序 | 起始 KPOINTS | 起始 NBANDS | 决策逻辑 |
|---|---|---:|---:|---|
| Si | Si | 8×8×8 Gamma | 64 | 小晶胞元素半导体；峰位分析前测试更密 k 点 |
| SiC | Si、C | 6×6×6 Gamma | 64 | 已验证 demo；定量峰位前测试 8×8×8 和 96/128 空带 |
| GaAs | Ga、As | 6×6×6 Gamma | 64 | 闪锌矿类半导体；确认 Ga/As 赝势系列和带隙处理 |

### SiC demo 的起始参数

| 参数 | DFT | LOPTICS | 含义 |
|---|---:|---:|---|
| `ENCUT` | 414 eV | 414 eV | 至少不低于 POTCAR 最大 `ENMAX`，还需收敛测试 |
| `KPOINTS` | 6×6×6 Gamma | 相同 | 布里渊区采样，随晶胞和收敛要求调整 |
| `EDIFF` | 1E-6 | 1E-8 | 电子收敛标准 |
| `NBANDS` | 64 | 64 | 空带范围，高光子能量需增加 |
| `ALGO` | Normal | Exact | DFT 和光学电子算法 |
| `LOPTICS` | 关闭 | 开启 | 独立粒子带间响应 |
| `CSHIFT` | — | 0.100 eV | 光谱展宽，不替代收敛测试 |
| `NEDOS` | — | 2000 | 频率网格分辨率 |
| `ISTART/ICHARG` | — | 1/11 | 读取 DFT 的 WAVECAR/CHGCAR |

程序不会因为参数和 SiC 默认值不同就自动拒绝；但会阻止缺文件、元素顺序错误、
非 Gamma KPOINTS，或 `ENCUT < max(POTCAR ENMAX)` 的情况。profile 建议和实际配置
不同不是错误，但必须记录原因，并在解释峰位前进行收敛测试。

## Workflow

### 1. 检查输入和 profile

```bash
python <skill-path>/scripts/config_loader.py --config config.yaml --check
```

程序报告材料、匹配的 profile、POTCAR 元素顺序、每个赝势的 `TITEL/ENMAX/ZVAL`、
最大 ENMAX、KPOINTS 网格，以及需要用户复核的参数建议。

### 2. 准备新运行目录

```bash
python <skill-path>/scripts/prepare.py --config config.yaml
```

程序创建 `00_DFT/` 和 `01_LOPTICS/`，复制 POSCAR/POTCAR/KPOINTS，并生成带材料名的
两个 INCAR。目标目录已存在时拒绝覆盖。

### 3. 运行 DFT 和 LOPTICS

```bash
python <skill-path>/scripts/run.py --config config.yaml
```

运行前检查 VASP、MPI、oneAPI 和旧输出文件；先运行 DFT，检查 `OUTCAR/WAVECAR/CHGCAR`，
再将 WAVECAR/CHGCAR 交给 LOPTICS。LOPTICS 必须产生 `OUTCAR/vasprun.xml/WAVECAR/WAVEDER`，
并包含实部、虚部频率相关介电函数和最终 timing 标记。

### 4. 提取能量域光学量

```bash
python <skill-path>/scripts/extract.py --config config.yaml
```

程序从配置指定的介电函数响应中读取能量、epsilon1 和 epsilon2，计算 n、k、alpha、R，
写入 `<prefix>_optical_properties.csv` 和六张能量域图。`alpha_cm-1` 是吸收系数，不是
样品厚度相关的吸收百分比。

### 5. 生成波长域结果

```bash
python <skill-path>/scripts/plot.py --config config.yaml
```

使用 `lambda_nm = 1239.841984 / energy_eV`，删除零能量点、按波长排序，写入波长 CSV
和六类波长图；同时生成吸收系数和反射率的窗口图。因此 `alpha(lambda)` 和 `R(lambda)`
是明确的输出，而不是只存在于原始 XML 中。

### 6. 只读验证

```bash
python <skill-path>/scripts/validate.py --config config.yaml
```

验证器不运行 VASP、不删除文件、不修改结果。它检查 VASP 文件、介电函数、选定响应、
CSV 列、有限数值、能量/波长排序、`n/k/alpha >= 0`、`0 <= R <= 1` 以及所需图片。
成功时输出 `VALIDATION=PASS`。

## Common Pitfalls

1. 没有 POTCAR 或元素顺序错误：按 POSCAR 顺序准备同一赝势系列，不要手工编辑 POTCAR。
2. `ENCUT` 小于 POTCAR 最大 ENMAX：提高 ENCUT 或记录为有意的收敛测试。
3. 把其他材料的 KPOINTS 直接复制过来：根据晶胞大小、维度和目标性质重新判断。
4. oneAPI/MPI 不可用：停止并修复环境，不要忽略加载失败。
5. LOPTICS 交接不一致：DFT 和 LOPTICS 的 POSCAR、POTCAR、KPOINTS、自旋设置、NBANDS
   必须兼容。
6. 把 alpha 当成吸收百分比：alpha 单位是 `cm^-1`，需要厚度和光学几何才能得到吸收率。
7. 可见光曲线看起来很平：先查看完整 UV 范围和对数纵坐标，不要仅凭图片判断失败。
8. profile 名称与实际 POSCAR/POTCAR 不符：以实际输入文件为准，修复 `expected_elements`。
9. 直接套用 SiC 网格到 Si 或 GaAs：profile 只是起始建议，峰位定量前必须做 k 点收敛。
10. 把 PBE LOPTICS 当成实验带隙：报告泛函和赝势，必要时单独做带隙修正研究。

## Verification Checklist

- [ ] POSCAR、POTCAR、KPOINTS 存在。
- [ ] POSCAR/POTCAR 元素顺序和数量一致。
- [ ] 已记录 POTCAR 的 TITEL、ENMAX、ZVAL。
- [ ] KPOINTS 是 Gamma-centered 且与配置一致。
- [ ] ENCUT 不低于最大 POTCAR ENMAX，或已记录有意的测试原因。
- [ ] 已选择 profile，并记录实际配置与 profile 建议的差异。
- [ ] DFT 有非空 OUTCAR、WAVECAR、CHGCAR。
- [ ] LOPTICS 有非空 OUTCAR、vasprun.xml、WAVECAR、WAVEDER。
- [ ] OUTCAR 包含实部和虚部频率相关介电函数。
- [ ] 能量域和波长域 CSV 都包含 epsilon1/epsilon2/n/k/alpha/R。
- [ ] 存在 alpha(lambda) 和 R(lambda) 图。
- [ ] n、k、alpha 非负，R 在 [0, 1] 内。
- [ ] `validate.py` 输出 `VALIDATION=PASS`。
- [ ] 结果明确标记为独立粒子 LOPTICS，没有声称 GW/BSE/声子结果。
- [ ] 在定量解释峰位前完成相应的 k 点、NBANDS、ENCUT/CSHIFT 收敛检查。
