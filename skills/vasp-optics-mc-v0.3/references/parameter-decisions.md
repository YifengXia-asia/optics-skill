# v0.3 材料适配和参数决策

## 1. 三个起始 profile

| profile | 元素 | 起始网格 | 适用判断 |
|---|---|---|---|
| `Si` | Si | 8×8×8 Gamma | 小晶胞元素半导体 |
| `SiC` | Si、C | 6×6×6 Gamma | 已验证的二元半导体 demo |
| `GaAs` | Ga、As | 6×6×6 Gamma | VASP 常见闪锌矿类半导体示例 |

profile 只提供起始建议。实际计算必须以用户给出的 POSCAR、POTCAR、KPOINTS、
目标能量范围和收敛测试为准。未知材料使用 generic profile：不自动猜测自旋、SOC、
金属展宽、U 值或结构类型，缺信息时停止询问。

## 2. 输入检查的决策顺序

1. 读取 POSCAR 的元素名（VASP5 格式）或使用 `expected_elements` 解释 VASP4 格式。
2. 读取 POTCAR 的 TITEL 区块，得到元素顺序、赝势系列、ENMAX 和 ZVAL。
3. 比较 POSCAR/POTCAR 的元素顺序和区块数量。
4. 读取 KPOINTS，确认 Gamma-centered、网格和偏移。
5. 比较配置的 ENCUT 和 POTCAR 最大 ENMAX；若太低则阻断。
6. 根据实际元素匹配 Si、SiC、GaAs profile，并报告推荐 KPOINTS/NBANDS。
7. 若用户配置与推荐不同，允许继续，但记录理由和收敛测试计划。

## 3. ENCUT 逻辑

```text
max_enmax = max(每个 POTCAR 区块的 ENMAX)
ENCUT >= max_enmax
```

ENCUT 不是从材料名称猜出来的，而是从实际 POTCAR 读取。正式计算应在目标性质
上做 ENCUT 收敛，而不是只满足最低值。

## 4. KPOINTS 逻辑

- 小晶胞三维半导体：从 6×6×6 或 8×8×8 开始，再做加密测试；
- 大超胞：可以降低网格，但必须记录晶胞尺寸和理由；
- 二维材料：通常第三方向为 1，并检查真空层；
- 分子/孤立体系：通常 Gamma-only；
- 金属：需要独立的展宽和 k 点策略，不直接套用本 Skill。

当前程序先检查实际 KPOINTS 是否与配置一致；profile 建议用于提示，不会替用户
自动改写 KPOINTS。

## 5. NBANDS 逻辑

LOPTICS 需要空带。目标光子能量越高，所需 NBANDS 通常越多。64 是 demo 起点；SiC
已知需要在解释高能峰前比较 96/128。Si、GaAs 也应根据目标能量范围做相同测试。

## 6. 响应类型

默认读取 `density-density` 区块。`vasprun.xml` 可能同时含有 `current-current`，但
两者不是可以无标签混用的同一列数据。报告中必须记录实际选择的 response。

## 7. 结果验证逻辑

验证分五层：

1. 文件层：OUTCAR、vasprun.xml、WAVECAR、WAVEDER、CSV、PNG 存在且非空；
2. 运行层：OUTCAR 有实部/虚部介电函数和最终 timing；
3. 解析层：XML 有选定 response，CSV 有全部列；
4. 数值层：能量/波长有序，n/k/alpha 非负，R 在 0 到 1；
5. 物理边界层：明确这是独立粒子 LOPTICS，不冒充 GW/BSE 或总静态介电响应。

## 8. 三个示例的限制

Si、SiC、GaAs profile 都假定非磁、无 SOC、绝缘/半导体、三维周期体系。
如果输入是金属、磁性材料、强 SOC 材料、二维材料或带电缺陷，必须先建立新的
profile 和 INCAR 决策，不应只换材料名继续运行。
