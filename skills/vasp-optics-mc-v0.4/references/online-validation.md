# 在线同体系验证方法

## 目录

1. 先确定可比条件
2. 搜索顺序
3. 比较项目
4. 报告模板

## 1. 先确定可比条件

从 POSCAR 和 POTCAR 记录：化学式、晶相/空间群（若能确认）、晶格常数、元素顺序、POTCAR 家族、交换-相关泛函、是否自旋和 SOC、目标能量范围。只比较同组成、同晶相和尽量相同计算近似的数据。不同多型、不同应变或不同泛函的数据必须标注为“非严格可比”。

## 2. 搜索顺序

优先使用：

1. VASP 官方 wiki/tutorial 或官方示例；
2. 原始论文和补充材料（DOI）；
3. Materials Project、AFLOW 等公开数据库的结构/带隙/介电条目；
4. 教科书或综述只作背景，不作为唯一数值依据。

建议查询式：

```text
"<formula>" "<phase>" dielectric function VASP
"<formula>" "<phase>" optical properties epsilon2
"<formula>" lattice constant band gap PBE
"<formula>" refractive index absorption coefficient
```

网页检索由具备联网能力的代理执行；服务器上的脚本不假设有公网，也不把网页数值自动写入 VASP 输入。

## 3. 比较项目

- 结构：晶格常数、体积、晶相；
- 电子：带隙或金属态、费米能级、是否需要 SOC/磁性；
- 光学：`epsilon1/epsilon2` 峰的大致能区、静态介电常数趋势、`n/k` 非负性；
- 工程量：吸收系数单位、反射率范围、波长方向是否正确。

不要因单个峰位或绝对值不同就判定失败。先检查泛函带隙、空带数、K 点、展宽、晶相和张量方向是否一致。

## 4. 报告模板

```markdown
# <formula> 在线合理性检查

- 计算体系：<formula>, <phase>, <functional>, <POTCAR family>, SOC=<yes/no>
- 计算窗口：<energy/wavelength>
- 来源：<official URL or DOI>
- 可比项目：<structure / gap / epsilon / n / k / alpha / R>
- 观察：<agreement or difference>
- 差异原因：<functional, phase, broadening, NBANDS, etc.>
- 结论：合理性对照，不替代收敛测试
```
