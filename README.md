# VASP 光学 Skill

本仓库提供从 VASP DFT 到独立粒子 LOPTICS、光学量提取和只读验证的可复用 Skill。

## 版本

- `skills/vasp-sic-optics-stage1-mc-v0.2/`：最初的可配置 SiC 阶段一流程。
- `skills/vasp-optics-mc-v0.3/`：保留了 Si/SiC/GaAs 起始 profile 的过渡版本。
- `skills/vasp-optics-mc-v0.4/`：当前推荐版本。它不按材料名称硬匹配，而是从 POSCAR/POTCAR/KPOINTS 分类体系，给出可审阅的参数建议，确认后才允许准备和运行。

## v0.4 快速使用

```bash
cd skills/vasp-optics-mc-v0.4
cp config.yaml.example config.yaml
# 将 POSCAR、POTCAR、KPOINTS 放入 config.yaml 的 input_dir
python scripts/config_loader.py --config config.yaml --inspect
# 审阅分类和建议后，在 config.yaml 中设置 confirm_recommendations: true
python scripts/config_loader.py --config config.yaml --check
python scripts/prepare.py --config config.yaml
python scripts/run.py --config config.yaml
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

`references/parameter-decisions.md` 解释分类和参数公式，`references/online-validation.md` 规定如何查找同组成、同晶相、同近似的权威对照。SiC 的 VASP 官方在线对照记录在 `validation/online/SiC.md`。

## 适用边界

默认流程是三维周期体系的独立粒子光学响应。GW、BSE、SOC、强磁性、金属专用光学、二维/表面真空归一化、声子/离子介电响应和结构优化需要单独的物理方案，不应只换材料名称继续运行。
