# VASP 光学 Skill

本仓库提供从 VASP DFT 到独立粒子 LOPTICS、光学量提取和只读验证的可复用 Skill。

## 版本

- `skills/vasp-sic-optics-stage1-mc-v0.2/`：最初的可配置 SiC 阶段一流程。
- `skills/vasp-optics-mc-v0.3/`：保留了 Si/SiC/GaAs 起始 profile 的过渡版本。
- `skills/vasp-optics-mc-v0.4/`：首次不按材料名称硬匹配的通用版。
- `skills/run-vasp-optics-adaptive-v0-7/`：当前推荐版本。它先按晶格/KPOINTS 判断 3D/2D/1D/孤立结构候选，再用基态本征值判断金属/半导体/绝缘体；用户需要通过两次确认门。

## v0.7 快速使用

```bash
cd skills/run-vasp-optics-adaptive-v0-7
cp config.yaml.example config.yaml
# 将 POSCAR、POTCAR、KPOINTS 放入 config.yaml 的 input_dir
# 如果已有完整基态，可将 input_dir 和 existing_dft_dir 指向该基态目录；源目录只读
python scripts/preflight.py --config config.yaml
python scripts/config_loader.py --config config.yaml --inspect
# 审阅分类和建议后，在 config.yaml 中设置 confirm_recommendations: true
python scripts/config_loader.py --config config.yaml --check
python scripts/prepare.py --config config.yaml
python scripts/run.py --config config.yaml --stage dft
# 审阅 system_classification.json；确认后设置 confirm_electronic_classification: true
python scripts/run.py --config config.yaml --stage loptics
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

三类型实跑过程和已知限制见 `validation/type-adaptation-v0.7/server-test-report.md`。仓库不包含 POTCAR、WAVECAR 或其他受许可证/隐私限制的完整计算文件。

## 适用边界

默认流程是独立粒子 LOPTICS。GW、BSE、严格二维极化率、声子/离子介电响应和结构优化需要单独的物理方案。2D/1D/孤立超胞可用于技术验证，但不能把三维超胞归一化结果直接称为低维内禀光学常数。
