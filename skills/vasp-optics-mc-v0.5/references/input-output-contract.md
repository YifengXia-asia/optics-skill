# 输入和输出契约

## 输入

`run.input_dir` 必须指向同一个目录。`POSCAR`、`POTCAR`、`KPOINTS` 是唯一的用户必需 VASP 输入；`config.yaml` 是流程控制文件，不替代这三个文件。

| 项目 | 类型/范围 | 由谁提供 | 失败时的含义 |
|---|---|---|---|
| `POSCAR` | VASP 4/5 文本；3 个晶格向量和正整数原子数 | 用户 | 无法判断晶胞、元素数量或体系维度 |
| `POTCAR` | 一个或多个连续赝势块；每块含 `TITEL/ENMAX/ZVAL` | 用户/管理员提供的官方 VASP 赝势库 | 无法确认元素、截止能量和价电子数 |
| `KPOINTS` | 显式 Gamma/Monkhorst-Pack 网格；三整数和可选偏移 | 用户 | 无法复现 Brillouin 区采样 |
| `config.yaml` | YAML；路径、环境、参数和确认闸门 | 技能模板+用户审阅 | 无法决定是否允许准备/运行 |

## CSV 字段

`<prefix>_optical_properties.csv` 的一行对应一个光子能量点，不是把 2000 行相加。`plot.py` 重新计算波长并排序后写出 `<prefix>_optical_properties_wavelength.csv`。

- `energy_eV`：VASP 频率网格的光子能量。
- `wavelength_nm`：由 `1239.841984 / energy_eV` 得到；零能量行应为空/NaN。
- `eps1_*`、`eps2_*`：复介电张量实部/虚部的 xx、yy、zz、xy、yz、zx 分量，直接来自 `vasprun.xml` 的 `real/imag` 数组。
- `eps1_avg`、`eps2_avg`：xx、yy、zz 三个对角分量的算术平均，用于后续各向同性曲线。
- `n`、`k`：由平均复介电函数计算的折射率和消光系数。
- `alpha_cm-1`：由 `k` 和角频率得到的吸收系数，单位 cm⁻¹；不是给定厚度后的吸收率。
- `reflectivity`：由 `n`、`k` 计算的法向入射界面反射率，理论检查范围为 0–1。

## 应该先看什么

1. 先看 `validate.py` 的 `VALIDATION=PASS`。
2. 再看 CSV 的列名、能量/波长范围和数值范围。
3. 再看 `OUTCAR` 的两段频率相关介电函数和最终 timing。
4. 最后看 PNG 的峰位和趋势。PNG 只用于可视化，不能替代 CSV 数值。
