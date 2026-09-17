# 12-ladderbill（阶梯电费）

Ladderbill — 居民阶梯电价分段累进（含尖峰系数）

## 启动

```bash
docker compose up --build
```

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |

## 主链

抄表录入 → 阶梯分段计费 → 账单明细

## 需量封顶（demand cap）

按户号 + 账期(YYYY-MM) 维护「账期需量 / 封顶阈值 / 超额折算系数」。
当需量超过阈值：`附加电量 = (需量 − 阈值) × 折算系数`，附加电量并入净电量后
再走阶梯与尖峰。未超阈值时附加电量为 0，字段仍照常返回。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/accounts/{id}/demand-caps` | 该户各账期封顶参数 |
| PUT | `/api/accounts/{id}/demand-caps/{period}` | 录入/更新（upsert），非法返回 422 `{code,field,message}` |
| POST | `/api/demand-cap/probe` | 只读探针：是否触发封顶、附加量、合并净电量与分段；不写运行、不改户参数 |
| POST | `/api/bill` | 计费；带 `account_id`+`period` 时自动并入附加电量，回包含 `base_kwh/extra_kwh/net_kwh/segments/demand_cap` |

校验错误码：`DEMAND_NEGATIVE`(demand_kw)、`CAP_ZERO`(cap_kw)、
`COEF_OUT_OF_RANGE`(convert_coef，合理范围 0~10)。


## 技术栈

Python 3.12 + FastAPI + SQLite；Vue 3 + Vite + Nginx。
