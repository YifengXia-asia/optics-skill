# SiC 在线合理性检查（v0.4 示例）

- 计算体系：SiC，用户已有的三维周期独立粒子 LOPTICS 结果
- 参考条件：VASP 官方 SiC dielectric-properties 示例；该示例明确要求先做标准 DFT、保留 WAVECAR，再进行频率相关响应。
- 参考起点：官方示例列出 Gamma-centered 6×6×6 KPOINTS，并在 IP LOPTICS 中使用 `ALGO=Exact`、`NBANDS=64`、`LOPTICS=.TRUE.`、`CSHIFT=0.100`、`NEDOS=2000`、`ISMEAR=0`、`SIGMA=0.01`。
- 官方输出检查：在 OUTCAR 中搜索频率相关 `IMAGINARY DIELECTRIC FUNCTION` 和 `REAL DIELECTRIC FUNCTION`；官方也说明这些结果可由 `vasprun.xml` 可视化。
- 结论：本地 SiC demo 的 DFT→WAVECAR→LOPTICS→介电函数→CSV/PNG 顺序与官方 IP 工作流一致。官方参数只能作为起始对照，不能替代本地 POTCAR、NBANDS、K 点和展宽收敛测试。

来源：

1. https://vasp.at/wiki/Dielectric_properties_of_SiC
2. https://vasp.at/tutorials/latest/response/part1/
3. https://vasp.at/wiki/Optical_properties_and_dielectric_response_-_Tutorial
