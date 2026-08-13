# v0.3 材料适配审查清单

## 三个首批示例

v0.3 使用三个 VASP 常见示例作为起始 profile：

| 材料 | 元素 | 起始网格 | 主要检查 |
|---|---|---|---|
| Si | Si | 8×8×8 | 元素半导体、k 点收敛、空带范围 |
| SiC | Si、C | 6×6×6 | 已验证 DFT→LOPTICS 流程、POTCAR 顺序 |
| GaAs | Ga、As | 6×6×6 | 闪锌矿结构、赝势系列、带隙处理 |

## 流程完整性

- [ ] 用户提供 POSCAR、POTCAR、KPOINTS。
- [ ] 先检查文件、元素顺序、ENMAX/ZVAL 和 KPOINTS，再生成 INCAR。
- [ ] 先运行 DFT，再检查 WAVECAR/CHGCAR，再运行 LOPTICS。
- [ ] LOPTICS 完成后才执行 XML 提取和波长转换。
- [ ] 最后执行只读验证，不把 PNG 存在当作科学正确性的唯一判据。

## 参数合理性

- [ ] ENCUT 来自实际 POTCAR 的最大 ENMAX，并计划收敛测试。
- [ ] KPOINTS 根据晶胞大小、维度和目标性质选择，而不是盲目复制 SiC。
- [ ] NBANDS 覆盖目标光子能量，并对高能峰做 96/128 等测试。
- [ ] CSHIFT 只作为展宽参数，不替代 k 点或空带收敛。
- [ ] 若是金属、磁性、SOC、二维或带电体系，已停止当前 profile 并建立专用方案。

## 决策逻辑

- [ ] profile 与实际元素匹配，或明确使用 generic。
- [ ] `expected_elements` 与 POSCAR/POTCAR 顺序一致。
- [ ] 配置偏离 profile 建议时，记录偏离原因。
- [ ] 结果报告中记录 response、POTCAR TITEL、ENCUT、KPOINTS、NBANDS 和 CSHIFT。

## Pitfalls

- [ ] 没有 POTCAR 或 POTCAR 顺序错时会停止。
- [ ] ENCUT 低于 ENMAX 时会停止。
- [ ] KPOINTS 非 Gamma-centered 或与配置不符时会停止。
- [ ] oneAPI/MPI 不可用时不会静默继续。
- [ ] 已有输出文件时不会覆盖。
- [ ] alpha 被解释为吸收系数，不被误报为吸收百分比。
- [ ] PBE LOPTICS 不被误报为 GW/BSE 或实验带隙。

## 可执行验证

必须依次看到：

```text
CONFIG=VALID
PREPARE=OK
RUN=PASS
EXTRACT=OK
WAVELENGTH_POSTPROCESS=OK
VALIDATION=PASS
```

`VALIDATION=PASS` 代表流程、文件和基本数值检查通过；它仍然不能替代材料特定的
ENCUT、k 点、NBANDS、CSHIFT 收敛和实验/文献对比。
