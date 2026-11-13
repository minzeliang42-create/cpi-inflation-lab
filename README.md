# CPI Inflation Distribution & Dispersion

固定68类美国CPI研究网站。Python计算六组历史指标，Plotly展示交互图表，GitHub Actions检查BLS更新，GitHub Pages提供静态托管。预测区间已预留，数值留空。

## 当前交付

- 六组完整历史序列，均计算至2026-10。Measures、普通Diffusion从2019-01起，Acceleration从2020-01起，t-Diffusion从2023-12起。
- 六张图及各自历史表、CSV下载和一个汇总Excel；可按月份和代码查询全部68类明细。
- 2026-10价格为实际值，权重由2026-09权重与当月价格更新，标为provisional。
- 原Excel仅以只读方式导入。项目保留其SHA-256及清洗后输入；原文件没有被改动。没有把原工作簿放进待发布目录。
- 本地已实际连接BLS，70条价格序列及68类API权重均成功检查。BLS官网HTML网页在本机返回403，状态为degraded，现有日历保留官方网页核验缓存。详见`VALIDATION.md`。
- 本项目尚未部署。工作流默认关闭发布，等网站访问范围确认后启用。

## 本地运行

需要Python 3.12及以上。Windows PowerShell：

```powershell
cd 'D:\我的文档\Desktop\论文\cpi-inflation-lab'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m cpi.build
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

浏览器打开 `http://127.0.0.1:8765`。不要双击index.html，浏览器的本地文件限制会阻止JSON读取。`scripts/serve.ps1`可启动已构建的网站。

手动抓取和重新计算：

```powershell
python -m cpi.update
python -m unittest discover -s tests -v
```

现有输入已经随项目交付，日常运行不需要本地原Excel。需要重新导入时：

```powershell
python scripts/import_excel.py 'D:\我的文档\Desktop\CPI原始数据_20261112\CPI_Raw_Data.xlsx'
python -m cpi.build
```

重新导入是人工重置种子数据的操作，会替换项目内的`data/input/observations.csv`；原Excel保持不变。已经运行云端更新后，先保留当前输入版本再重导。

## 计算口径

价格为全国CPI-U NSA，固定排除SEHP、SEEA。68类每月归一化至100%。

1. `YoY = (P[t]/P[t-12]-1)*100`。Headline和Core分别来自CUUR0000SA0、CUUR0000SA0L1E，缺失时保留NA。
2. Acceleration为当月YoY减去12个月前YoY，单位pp。
3. 分位数：按数值稳定升序排序，用`np.interp([.1,.25,.5,.75,.9], cumulative_weight, sorted_value)`插值。权重为当月权重，端点钳制。不使用居中累计权重或跨过阈值的阶梯值。
4. 普通Diffusion使用严格YoY<0或YoY>0，单月值。零通胀另存于分项值，不归入上涨或下跌。
5. t-Diffusion窗口包含当月、完整60个日历月的YoY；均值、样本标准差ddof=1；严格Z<-2或Z>2。
6. 类别占比的分母固定68，权重占比使用满足条件类别自身的当月权重。

固定样本任何必需值缺失时，相应总体指标为NA，不删除类别重新缩小分母。权重分母为零、负权重、窗口不足或标准差为零均不会产生虚假的零值。同比不自动填充缺失价格。官方总指数基期缺失时保留NA，即使分项估算已齐。

`Estimated_Data`只导入已批准的2025-09、2025-10权重，2025-10价格和2025-11机动车保险价格。含“回测”的行不会参与正式结果。官方观察优先；新官方值取代估算值后，旧估算仍保留在来源账本。历史插值使用事后信息，在实时回测中需要单独控制数据可得日期。

## 更新与年度权重

- 70条价格序列以每批25条查询BLS v2，包含68类以及Headline、Core。查询最近两年，通常3次API请求；序列响应缺失、重复或最新月份不完整时拒绝发布新数据。
- API的`Relative Importance`属于该价格观察月的前一月。程序优先核对Table 2及Table 1的**Relative Importance列头**日期，绝不把新闻稿标题日期直接当作权重日期。Table 1只有大类，不足68类时不能代替详细表。
- Table HTML不可达时，API按已经核验的前一月口径继续检查，明确记录degraded状态。API不提供权重时保留现有权重，缺少新月权重则按规则暂定估算。
- 年度RI页面分别保存新旧权重版本及消费支出基期。新权重下的12月桥接权重独立存入`annual_anchors.json`，不覆盖旧阶段12月观察。只有明确标为新阶段、68类齐全的桥接权重才能在跨年时为1月暂定计算提供锚点；否则1月等待官方权重，不跨年机械滚动。
- 同一年度阶段内，`w_raw[i,t] = w[i,t-1]*P[i,t]/P[i,t-1]`，再归一化68类至100%。暂定原始值的口径为68类归一化百分比，明细逐行显示。
- API失败时尝试`cu.data.0.Current`官方批量价格。批量源或HTML同样失败时保留上次成功发布及失败记录。
- 原始响应按SHA-256归档，账本以月份、代码、类型、状态组成唯一键。修订保留前值、来源URL、抓取时间、可取得的HTTP发布时间和响应hash。来源未给出的发布时间留空，不用抓取时间冒充发布时间。
- 每次全量重算约数千行，直接覆盖所有受估算替换、12/24个月滞后或60个月窗口影响的历史指标。验证后切换版本指针，失败时回滚指针及输入账本。不会清空旧的发布包。

`dist/current.json`指向当前不可变数据包。图表、表格读取该包的research.json，CSV与Excel从同一DataFrame生成，下载一致性由测试逐值核对。独立的`dist/status.json`在失败时仍能展示状态。保留的数据版本会逐渐增加，可按研究留档要求定期归档旧发布包和原始响应。

## 部署到GitHub

先确定**网站**公开还是私密，以及目标GitHub账号/仓库。私有仓库不自动意味着Pages网站私密。GitHub Pages公开/私密访问能力取决于账号、组织与套餐；需要登录控制时应先核对可用能力，必要时采用带身份验证的静态托管。

1. 在目标账号建立仓库，把此目录内容上传到`main`。保留`.github`目录。提交清洗后的`data`、生成的`dist`及代码；排除`.venv`、`.staging`、`output`、`.env`和任何凭据。
2. 在仓库Settings → Actions → General允许工作流读写内容。Actions需要能提交数据变更；若main受分支保护，配置专用可写分支或机器人权限。
3. 在Settings → Pages选择GitHub Actions作为构建发布来源，确认网站访问范围。
4. 可选：在Settings → Secrets and variables → Actions中添加`BLS_API_KEY` Secret。API密钥只从环境读取。当前已实测无密钥批量API可以返回所需数据；将来限制改变时在Secret中配置即可。
5. 确认网站访问设置后，建立Repository variable：`CPI_PAGES_ENABLED=true`。未设置时，工作流计算和归档数据，但不部署网站。
6. 在Actions中手动运行“Update CPI research and deploy”。检查更新日志、测试和Pages deployment成功后，用工作流返回的真实网址验证。

工作流每日UTC 22:25（北京时间次日06:25）检查一次。工作日UTC 12:40–18:40逐小时触发一次轻量本地日历判断，仅在官方发布日期的发布后5小时内发出额外BLS请求。冬夏令时由America/New_York转换；非发布日期不额外抓取。GitHub定时任务可能排队延迟，不能当作秒级发布承诺。公开仓库若长期无活动，需留意GitHub对定时工作流的停用政策。

日历解析失败时保留上次日历并给出告警；缓存已无未来日期时顶部显示等待官方日历。网页无法访问时，应在GitHub Actions检查网络、API限制和HTML结构，修复后手动运行。失败工作流仍保留上一版研究结果并可发布失败状态。

部署成功后，本地电脑可以关闭，数据抓取、计算、测试和发布均由GitHub云端运行。

## 目录

```text
cpi/                   导入、计算、构建和官方更新
web/                   HTML / CSS / JS及本地Plotly
data/input/            固定类别、观察账本、源文件hash与日历
data/raw/              BLS响应归档
data/updates/          更新状态、来源和修订日志
data/annual/           年度新旧权重版本记录
dist/                  可直接部署的静态网站及版本化下载文件
tests/                 独立复算、边界条件和导出一致性测试
.github/workflows/     云端定时更新和Pages发布
```

## 官方参考

- [BLS API文档](https://www.bls.gov/developers/api_signature_v2.htm)
- [BLS月度Table 1](https://www.bls.gov/news.release/cpi.t01.htm)、[详细Table 2](https://www.bls.gov/news.release/cpi.t02.htm)
- [年度Relative Importance及价格更新方法](https://www.bls.gov/cpi/tables/relative-importance/)
- [官方CPI发布日期](https://www.bls.gov/schedule/news_release/cpi.htm)
- [SF Fed PCE网站：信息组织参考](https://www.frbsf.org/research-and-insights/data-and-indicators/pce-personal-consumption-expenditure-price-index-pcepi/)
- [GitHub Pages说明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
