# 云端部署及验收

网站：https://minzeliang42-create.github.io/cpi-inflation-lab/

2026-11-16已启用GitHub Pages（GitHub Actions发布源），并实际打开真实网址验收。

手动更新运行：https://github.com/minzeliang42-create/cpi-inflation-lab/actions/runs/43734621054

该运行的research和deploy均成功。BLS价格及68类API月度权重检查成功时间：2026-11-16 00:17:50（Asia/Shanghai），新增或修订0条；数据仍覆盖至2026-10。BLS新闻稿、年度权重和日历HTML返回403，网站状态明确为degraded；API更新及既有数据继续可用。

线上确认6张Plotly图、7张数据表、68类分项；六组历史表月数分别为94、82、94、94、35、35；历史范围切换、悬停数值、2025-10机动车保险估算标记和全部CSV/Excel下载均通过。390px移动端无页面横向溢出。16项计算及导出一致性测试在云端通过。

计划：每日UTC 22:25检查（北京时间次日06:25）；官方发布日增加检查频率。手动更新入口为Actions中的Run workflow。源Excel保持不变；未来预测值留空。
