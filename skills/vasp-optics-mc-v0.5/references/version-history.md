# 版本记录

## v0.5

- 补充 POSCAR/POTCAR/KPOINTS、config、VASP 产物和 CSV/PNG 的精确契约。
- 统一 `eps1/eps2/n/k/alpha_cm-1/reflectivity` 术语，并说明它们的来源和物理含义。
- 为 inspect/check/prepare/run/extract/plot/validate 增加可读的成功/失败状态码和停止处理。
- 增加缺文件、确认闸门、重复输出目录、非体相/金属/磁性/SOC 候选等正反例。
- 明确 Linux/Unix 运行边界以及 Python 后处理依赖；保留 v0.4 供回退。

## v0.4

首次按输入体系分类，不使用材料名称作为参数分支；增加 KPOINTS/POTCAR 顺序检查、能量域和波长域后处理及只读验证。
