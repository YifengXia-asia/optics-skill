# SiC v0.2 验证记录

## 验证目标

验证 `vasp-sic-optics-stage1-mc-v0.2` 是否能够完整执行：

```text
输入检查 → 准备 DFT/LOPTICS → DFT → LOPTICS → 光学提取 → 波长后处理 → 只读验证
```

## 输入

使用一个新的运行目录，不覆盖原始计算：

```text
输入来源：用户自己的 POSCAR、POTCAR、KPOINTS
材料：SiC
POTCAR 顺序：Si → C
ENCUT：414 eV
KPOINTS：6×6×6 Gamma-centered
NBANDS：64
MPI：4 核
响应：density-density
```

本次服务器验证使用的环境为：

```text
VASP：6.3.2
VASP 可执行文件：/home/xyf/vasp/vasp.6.3.2/bin/vasp_std
oneAPI：/opt/intel/oneapi/setvars.sh
后处理环境：conda vasp
```

服务器上的绝对路径只出现在本次验证记录中，不写入 Skill 的通用配置模板。

## 执行步骤

```bash
python <skill-dir>/scripts/config_loader.py --config config.yaml --check
python <skill-dir>/scripts/prepare.py --config config.yaml
python <skill-dir>/scripts/run.py --config config.yaml
python <skill-dir>/scripts/extract.py --config config.yaml
python <skill-dir>/scripts/plot.py --config config.yaml
python <skill-dir>/scripts/validate.py --config config.yaml
```

其中：

1. `config_loader.py` 检查 POSCAR、POTCAR、KPOINTS、ENMAX、ZVAL 和元素顺序。
2. `prepare.py` 创建 `00_DFT` 和 `01_LOPTICS`，并生成两个 INCAR。
3. `run.py` 先运行 DFT，再把 WAVECAR/CHGCAR 交给 LOPTICS。
4. `extract.py` 从 `vasprun.xml` 读取介电函数并计算 epsilon1、epsilon2、n、k、alpha、R。
5. `plot.py` 把能量转换为波长，并生成吸收系数和反射率的波长图。
6. `validate.py` 只读检查 VASP 输出、CSV、PNG 和数值范围。

## 实际服务器结果

运行目录：

```text
/home/xyf/vasp/SiC_dielectric/v02_validation/
```

验证输出：

```text
CONFIG=VALID
PREPARE=OK
RUN=PASS
EXTRACT=OK;MATERIAL=SiC;RESPONSE=density-density;ROWS=2000;ENERGY=0:146.797
WAVELENGTH_POSTPROCESS=OK;ROWS=1999;RANGE_NM=8.44595:16891.6
VALIDATION=PASS;MATERIAL=SiC;ROWS=2000;RESPONSE=density-density
```

## 关键结果文件

在服务器运行目录的 `01_LOPTICS/` 中生成：

```text
SiC_v02_optical_properties.csv
SiC_v02_optical_properties_wavelength.csv
SiC_v02_epsilon1.png
SiC_v02_epsilon2.png
SiC_v02_n.png
SiC_v02_k.png
SiC_v02_alpha.png
SiC_v02_R.png
SiC_v02_eps1_vs_wavelength.png
SiC_v02_eps2_vs_wavelength.png
SiC_v02_n_vs_wavelength.png
SiC_v02_k_vs_wavelength.png
SiC_v02_alpha_vs_wavelength.png
SiC_v02_R_vs_wavelength.png
```

同时确认存在：

```text
OUTCAR
vasprun.xml
WAVECAR
WAVEDER
```

`alpha(λ)` 和 `R(λ)` 分别表示吸收系数和正入射反射率随波长的变化。`alpha` 是 `cm^-1`，不是样品厚度相关的吸收百分比。

## 判定标准

只有同时看到以下结果，才认为流程完整跑通：

```text
CONFIG=VALID
PREPARE=OK
RUN=PASS
EXTRACT=OK
WAVELENGTH_POSTPROCESS=OK
VALIDATION=PASS
```

这证明流程和文件输出正确，但不代替 ENCUT、KPOINTS、NBANDS 的科学收敛测试。
