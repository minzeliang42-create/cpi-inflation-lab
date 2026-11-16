# V1.1修订验收（2026-11-16）

站点：https://minzeliang42-create.github.io/cpi-inflation-lab/

## 修改与六组图表核对

已实际打开SF Fed参考页面并读取六张官方图（pce_chart1.png至pce_chart6.png）。其Acceleration图含Total、Core、Median三条线和三段分位数阴影；我们的CPI版本已补齐官方整体、核心加速度。PCE图3/4文字标注3MMA，本CPI项目按既定方法保留单月值。

| 图组 | V1.1结构、单位和时间起点 | 验收 |
|---|---|---|
| CPI Measures | Headline、Core、Median；三段P10/25/75/90阴影；%；2019-01 | 保留 |
| Acceleration | 官方Headline、Core同比差及Median；相同阴影；pp；2020-01 | 两条新序列同步进入JSON、CSV、Excel、悬停、表格、最新卡片 |
| Diffusion Declines | 类别/权重两条曲线；%；2019-01；0–100% | 保留单月值 |
| Diffusion Growth | 类别/权重两条曲线；%；2019-01；0–100% | 保留单月值 |
| t-Diffusion Declines | 类别/权重两条曲线；%；2023-12；动态纵轴 | 从0起，展示窗口最大值上浮15%并向上取整 |
| t-Diffusion Growth | 同上 | 同上 |

所有图保留图例、月份时间轴、悬停、历史表、最新月份及方法说明。普通Diffusion的0–100%不变。t-Diffusion历史仅35个月，因此3Y、5Y与All覆盖相同数据，不应人为制造差异。缩放至较短区间时也会重算纵轴；全部区间保留原始数据及峰值。当前All范围Declines上限5.1%、Growth上限6.8%，原上限均100%。

Official、Estimated、Provisional、Forecast分别定义为官方观测、批准的历史估算、已公布价格下的暂定权重、模型预测。本轮无Forecast数值。图底状态条、悬停、历史表及最新月说明同时提示估算价格依赖；2026-10同时含Provisional权重和2025-10插值基期。t-Diffusion状态追溯完整60个月同比窗口。

## 数据复算及对账

未改原Excel，读取后hash一致。当前远程输入与本地原工作簿导入观察没有数值修订。使用四个重点月的源价格/权重字典、math.fsum、statistics.stdev及手写标量分位数独立复算六组指标。2026-10权重独立由2026-09权重乘当月价格比推算。

原有数值字段比较：2272项；最大绝对差8.88e-16个百分点。五个分位数、普通/异常Diffusion均保持原结果。新增两条官方Acceleration不替代分项结果；只读取官方指数，官方基期缺失继续NA。CSV、Excel、JSON统一由同一DataFrame输出；界面数值按显示精度取舍，底层不做额外舍入。

| 月份 | 新增Headline Acceleration pp | 新增Core Acceleration pp | 原Median Acceleration pp（不变） |
|---|---:|---:|---:|
| 2024-12 | -0.464065611 | -0.691708385 | -1.549173142 |
| 2025-10 | NA | NA | -0.774478842 |
| 2026-09 | 0.725007954 | -0.454865651 | -0.524299522 |
| 2026-10 | NA | NA | -0.078735559 |

四个月全部六组详细结果见[VALIDATION_V1_1.json](VALIDATION_V1_1.json)。该JSON由计算生成，不是验收参考值硬编码。

## 官方更新与年度权重

本轮实测BLS API返回CUUR0000SEFA的M10 2026价格290.371及`aspects[name=Relative Importance]`为0.309，其实际权重月份为2026-09。排除`Relative Importance for previous year`的0.315。每次更新新增字段/所属月份/68类完整性审计；成功状态分开记录价格和权重，不把缺少权重的检查称为成功。

新闻稿Table 2、官方打印入口、cu.aspect官方批量权重、年度RI、官方发布日历和bls.ics均实测403。本轮未引入第三方或把估算冒充官方。官方来源检查结果保存在data/updates/official-channel-audit-v1.1.json，原始响应按hash留档。网络超时也记入日志。表头与API权重出现数值/月份矛盾时停止更新并回滚，不降级发布冲突值。

跨年若没有明确新阶段December桥接权重则不推算January；新旧年度权重分别保存，CPI-U/CPI-W列序不符则拒绝解析。新官方权重按优先级自动替代暂定权重，全量重算受影响的滞后/滚动窗口。失败保持上版有效结果和输入账本。

## 测试与部署

本地21项Python测试通过；云端跳过仅本地存在的私人原Excel检查，其余测试执行。新增Node纵轴测试覆盖全历史、限定区间、区间外峰值、零值、缺失及普通Diffusion固定范围。JSON/CSV/Excel逐值一致性包含两条新Acceleration列。后续运行入口及部署结果见GitHub Actions和DEPLOYMENT.md。

运行：`python -m cpi.build`、`python -m unittest discover -s tests -v`、`node tests/test_frontend.mjs`。


## 实际上线验收结果

V1.1提交：05d037992488f9e8d39f31aac2c2944c448e8e86。

[GitHub Actions运行43789122561](https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43789122561)：research、deploy均success。Python运行21项，20项通过，1项原始私人Excel检查仅在本地执行、云端跳过；Node纵轴边界测试通过。最新BLS检查时间为北京时间2026-11-16 09:56:41，更新0条观察，渠道状态degraded。

已实际打开公网网址，确认meta.app_version=1.1、6张Plotly图、94/82/94/94/35/35个月历史表和68类查询。新增Acceleration曲线、图例、悬停pp值、历史表列均在公网显示。六组CSV下载及Excel下载均HTTP 200，Excel ZIP文件签名PK正确。界面表格和卡片分别显示3位、2位小数，下载文件保留完整计算精度。

实际点击两张t-Diffusion的3Y、5Y、All按钮，纵轴分别保持0–5.1%和0–6.8%（因为仅35个月历史）；较短可见区间另测会调整上限，普通Diffusion仍0–100%。390px移动端页面宽度375px，六张图宽338.67px，无页面横向溢出；桌面1342px布局正常；浏览器控制台0错误。

本次浏览器自动截图接口超时，布局验收基于实际页面元素、交互、图表数据及尺寸检查；没有生成本轮视觉截图文件。六张SF Fed原图已实际读取，核对记录见上文。
