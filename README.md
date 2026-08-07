# VASP 光学 Skill

这是一个面向 VASP 独立粒子光学计算的 Skill 仓库。

## 内容

- `skills/vasp-sic-optics-stage1-mc-v0.2/`：可配置的 VASP DFT → LOPTICS → 光学后处理 Skill。
- `validation/sic-v0.2/`：SiC 验证流程、配置模板、可复用验证脚本和结果摘要。

Skill 的默认示例是 SiC，但 v0.2 允许用户修改材料名、输出前缀、POSCAR/POTCAR/KPOINTS、ENCUT、NBANDS 和路径。程序会检查 POSCAR/POTCAR 顺序、POTCAR 的 ENMAX/ZVAL 以及 Gamma-centered KPOINTS。

## 快速使用

```bash
cd skills/vasp-sic-optics-stage1-mc-v0.2
cp config.yaml.example config.yaml
# 编辑 config.yaml 中的输入目录、输出目录和服务器环境
python scripts/config_loader.py --config config.yaml --check
python scripts/prepare.py --config config.yaml
python scripts/run.py --config config.yaml
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

完整规则请阅读 Skill 目录中的 `SKILL.md`；可复现验证说明见 `validation/sic-v0.2/README.md`。

## 适用边界

本仓库的流程是独立粒子 LOPTICS，不包含 GW、BSE、CHI/RPA、局域场、声子/离子介电、SOC、磁性或结构优化。
