# v0.2 参数决策与材料适配说明

## 1. 默认示例与可配置项

v0.2 的默认示例仍是小晶胞、非磁、绝缘 SiC：

```text
material = SiC
prefix = SiC
ENCUT = 414 eV
KPOINTS = 6×6×6 Gamma
NBANDS = 64
CSHIFT = 0.100 eV
NEDOS = 2000
response = density-density
```

这些是 demo 默认值，不是所有材料的固定值。换材料时至少重新检查
POSCAR、POTCAR、ENCUT、KPOINTS、NBANDS、ISPIN/SOC 和目标能量范围。

## 2. POTCAR 的来源和检查

VASP 不会根据 POSCAR 自动生成 POTCAR。用户应从已授权的赝势库选择同一
泛函系列的元素 POTCAR，并按 POSCAR 元素顺序拼接。不要手工编辑 POTCAR。

`config_loader.py` 会读取每个赝势块的：

- `TITEL`：赝势名称、泛函和版本，例如 `PAW_PBE Si_GW`；
- `ENMAX`：该赝势建议的平面波截断能；
- `ZVAL`：该赝势包含的价电子数。

当前 SiC demo 的实际文件为：

```text
PAW_PBE Si_GW 04May2012: ZVAL=4.000, ENMAX=245.345 eV
PAW_PBE C_GW 28Sep2005:  ZVAL=4.000, ENMAX=413.992 eV
```

所以 demo 使用 `ENCUT=414 eV`。`*_GW` 是赝势类型名称，不代表本次运行
执行了 GW；本次计算仍是 LOPTICS。正式工作应记录赝势类型，并确认它符合
课题组的泛函和精度要求。

## 3. ENCUT

最低安全起点通常不低于所有 POTCAR `ENMAX` 的最大值：

```text
ENCUT >= max(ENMAX in POTCAR)
```

随后应针对总能量、力和目标光谱范围做收敛测试。v0.2 不因用户选择与
SiC demo 不同的值就拒绝运行，但如果 ENCUT 低于实际最大 ENMAX，会给出
阻断性检查错误。

## 4. KPOINTS

当前 `6×6×6 Gamma` 只适合小晶胞 SiC 的快速基准。k 点应随晶胞大小、维度
和目标性质调整：大超胞可以更稀，二维材料通常使用 `N×N×1`，小晶胞和
精确峰位通常需要更密网格。程序检查实际 KPOINTS 的模式、网格和偏移是否
与 `config.yaml` 一致。

## 5. NBANDS、CSHIFT 和 NEDOS

- `NBANDS` 决定能访问的空带范围；提高目标光子能量时通常需要增加它。
- `CSHIFT` 是光谱平滑宽度，不是 k 点收敛的替代品。
- `NEDOS` 只改变频率采样密度，不会增加空带数量。

## 6. 六个输出量

对 `epsilon = epsilon1 + i*epsilon2`：

```text
n      = sqrt((|epsilon| + epsilon1)/2)
k      = sqrt((|epsilon| - epsilon1)/2)
alpha  = 2*omega*k/c，换算为 cm^-1
R      = ((n-1)^2 + k^2)/((n+1)^2 + k^2)
```

`alpha` 是吸收系数，不是吸收百分比；吸收百分比还需要样品厚度和光学
几何。`R` 是正入射 Fresnel 反射率。v0.2 同时输出能量域和波长域的
`epsilon1/epsilon2/n/k/alpha/R`。

## 7. 波长域

```text
lambda_nm = 1239.841984 / energy_eV
```

零能量点没有有限波长，应删除后按波长排序。输出包括：

- `<prefix>_optical_properties_wavelength.csv`
- `<prefix>_alpha_vs_wavelength.png`
- `<prefix>_R_vs_wavelength.png`
- 对应的 epsilon1、epsilon2、n、k 波长图

## 8. 适用边界

本 Skill 适合第一阶段电子独立粒子光学，不等于 GW/BSE 光学，也不包含
极性材料的声子/离子静态介电贡献。若用户要求 IR/THz 总静态介电常数、
SOC、磁性、金属展宽或结构优化，应先建立单独的材料/任务配置。
