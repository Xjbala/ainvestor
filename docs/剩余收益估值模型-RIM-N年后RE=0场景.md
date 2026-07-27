# 剩余收益估值模型（RIM）- N年后RE=0场景

## 1. 模型概述

### 1.1 核心原理

剩余收益模型（Residual Income Model, RIM）基于净资产的会计价值：

- 每股价值 V₀ = 初始每股净资产 BPS₀ + 未来剩余收益的现值
- 本场景假设N年后剩余收益归零（RE=0），即第N年及以后ROCE等于要求回报率

### 1.2 关键公式

**剩余收益计算：**

```
RE_t = EPS_t - r × BPS_{t-1}
```

其中：
- RE_t：第t年的剩余收益
- EPS_t：第t年的每股收益
- r：要求回报率（股权成本）
- BPS_{t-1}：第t-1年的每股净资产

**每股价值计算：**

```
V₀ = BPS₀ + Σ(PV(RE_t))
```

其中：
- PV(RE_t) = RE_t / (1+r)^t
- 求和从t=1到t=N

**情景估值计算（基于RE趋势分析）：**

```
# 步骤1：计算预测期（T1-TN）的RE序列
re_sequence = [RE₁, RE₂, ..., RE_N]

# 步骤2：分析RE趋势
re_trend = analyze_re_trend(re_sequence)

# 步骤3：根据趋势计算三种情景估值
if re_trend == 'decreasing':
    # 保守情景：RE递减，第N年RE接近0
    V₀_保守 = BPS₀ + Σ(PV(RE_t)) for t=1 to N
    V₀_基准 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值常数)
    V₀_乐观 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值增长)
elif re_trend == 'stable':
    # 基准情景：RE稳定，第N年RE保持常数
    V₀_保守 = BPS₀ + Σ(PV(RE_t)) for t=1 to N
    V₀_基准 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值常数)
    V₀_乐观 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值增长)
elif re_trend == 'increasing':
    # 乐观情景：RE递增，第N年RE继续增长
    V₀_保守 = BPS₀ + Σ(PV(RE_t)) for t=1 to N
    V₀_基准 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值常数)
    V₀_乐观 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值增长)
```

**情景说明：**

| 页面显示 | RE趋势 | 终值假设 | 商业含义 |
|---------|--------|---------|---------|
| **保守** | RE递减 → 接近0 | 第N年后RE=0 | 成熟期/衰退期公司，ROE下降到股权成本 |
| **基准** | RE稳定 → 保持常数 | 第N年后RE=常数 | 稳定增长公司，维持超额收益能力 |
| **乐观** | RE递增 → 持续增长 | 第N年后RE继续增长 | 高成长公司，持续创造超额价值 |

**核心改进：**
- 页面名称保持不变（保守/基准/乐观）
- 情景计算基于实际RE预测，不再是固定倍数
- 更符合剩余收益模型的本质和不同增长阶段的公司特征

---

## 2. 数据存储模式（核心）

### 2.1 数据库存储结构

财务数据存储在 `financial_data` 表中，采用**科目编码+报告期**的存储方式：

```
表名: financial_data
关键字段:
- company_code: 股票代码 (如 "000001")
- subject_code: 科目编码 (如 "ISF021" 表示净利润)
- report_date: 报告日期 (如 "2024-12-31")
- report_type: 报表类型 (BS/IS/CF/OE)
- value_decimal: 数值 (单位：万元)
```

### 2.2 科目编码映射

**ResidualIncomeService使用的科目编码：**

| 财务指标 | 科目编码 | 报表类型 | 说明 |
|---------|---------|---------|------|
| **基础数据（存储在数据库）** |
| 营业收入 | ISI001 | IS | 利润表科目 |
| 净利润 | ISF021 | IS | 利润表科目 |
| 资产总计 | BSA121 | BS | 资产负债表科目 |
| 负债合计 | BSL112 | BS | 资产负债表科目 |
| 归属于母公司所有者权益合计 | BSE010 | BS | 资产负债表科目 |
| 实收资本（或股本） | BSE001 | BS | 资产负债表科目 |
| **计算字段（不存储，实时计算）** |
| EPS | - | - | = 净利润 / 股本 |
| BPS | - | - | = 股东权益 / 股本 |
| DPS | - | - | = EPS × 股利支付率 |
| ROE | - | - | = EPS / BPS_{t-1} |
| RE | - | - | = EPS - r × BPS_{t-1} |

### 2.3 数据获取流程

**步骤1：确定基准报告期**

```python
# 查询最新的年报日期
report_date = SELECT report_date FROM financial_data 
              WHERE company_code = '000001' 
                AND report_type = 'IS'
              ORDER BY report_date DESC LIMIT 1
# 结果：2024-12-31
base_year = 2024
```

**步骤2：获取基准财务数据（T0）**

```python
# 从数据库获取基准年的基础数据
net_income = SELECT value_decimal FROM financial_data 
             WHERE company_code = '000001' 
               AND subject_code = 'ISF021' 
               AND YEAR(report_date) = 2024
             
shareholders_equity = SELECT value_decimal FROM financial_data 
                      WHERE company_code = '000001' 
                        AND subject_code = 'BSE010' 
                        AND YEAR(report_date) = 2024

shares_outstanding = SELECT value_decimal FROM financial_data 
                     WHERE company_code = '000001' 
                       AND subject_code = 'BSE001' 
                       AND YEAR(report_date) = 2024
```

**步骤3：计算T0的每股数据**

```python
current_eps = net_income / shares_outstanding
current_bps = shareholders_equity / shares_outstanding
current_dps = current_eps * payout_ratio
current_roe = current_eps / current_bps
```

**步骤4：预测T1-N的数据**

```python
# 使用增长率预测EPS，然后递推计算BPS和DPS
for t in 1 to N:
    projected_eps[t] = projected_eps[t-1] × (1 + growth_rate)
    projected_dps[t] = projected_eps[t] × payout_ratio
    projected_bps[t] = projected_bps[t-1] + projected_eps[t] - projected_dps[t]
```

---

## 3. 计算流程（完整版）

### 3.1 输入参数

| 参数 | 说明 | 数据来源 | 默认值 |
|------|------|----------|--------|
| **stock_code** | 股票代码 | 用户输入 | - |
| **base_year** | 基准年 | 自动查询最新年报 | 2024 |
| **cost_of_equity** | 要求回报率 | 用户输入 | 9.00% |
| **growth_rate** | 预测期增长率 | 默认/用户输入 | 15% |
| **terminal_growth_rate** | 永续增长率 | 默认/用户输入 | 3% |
| **projection_years** | 预测年数（N） | 默认/用户输入 | 5 |
| **payout_ratio** | 股利支付率 | 默认/用户输入 | 30% |
| **scenario** | 估值场景 | 'n_years_re_zero' | 'n_years_re_zero' |

### 3.2 从数据库获取的基准数据（T0）

| 财务科目 | 科目编码 | 获取SQL | 单位 |
|---------|---------|---------|------|
| 净利润 | ISF021 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='ISF021' AND YEAR(report_date)=base_year` | 万元 |
| 股东权益 | BSE010 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='BSE010' AND YEAR(report_date)=base_year` | 万元 |
| 股本 | BSE001 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='BSE001' AND YEAR(report_date)=base_year` | 万元 |

### 3.3 T0计算字段

| 指标 | 计算公式 | 示例值 |
|------|----------|--------|
| EPS₀ | 净利润 / 股本 | 0.73元/股 |
| BPS₀ | 股东权益 / 股本 | 3.58元/股 |
| DPS₀ | EPS₀ × 股利支付率 | 0.22元/股 |
| ROE₀ | EPS₀ / BPS₀ | 20.39% |

### 3.4 T1-N预测和计算流程

```
for t in 1 to N:
    # 1. 预测EPS（按增长率增长）
    EPS_t = EPS_{t-1} × (1 + growth_rate)
    
    # 2. 计算DPS（使用股利支付率）
    DPS_t = EPS_t × payout_ratio
    
    # 3. 计算BPS（递推）
    BPS_t = BPS_{t-1} + EPS_t - DPS_t
    
    # 4. 计算ROE
    ROE_t = EPS_t / BPS_{t-1}
    
    # 5. 计算剩余收益
    RE_t = EPS_t - r × BPS_{t-1}
    
    # 6. 计算折现因子
    discount_factor = (1 + r)^t
    
    # 7. 计算剩余收益现值
    PV_RE_t = RE_t / discount_factor
```

### 3.5 汇总计算

```
// 1. 计算剩余收益现值总和
total_PV_RE = Σ(PV_RE_t) for t=1 to N

// 2. 分析RE趋势
re_sequence = [RE₁, RE₂, RE₃, RE₄, RE₅]
re_trend = analyze_re_trend(re_sequence)

// 3. 计算终值（如果适用）
if scenario == 'n_years_re_zero':
    # N年后RE=0场景，不需要终值
    pv_terminal_value = 0
else:
    # 其他场景计算终值
    if re_trend == 'decreasing':
        # 保守：假设第N年后RE=0
        terminal_re = 0
        pv_terminal_value = 0
    elif re_trend == 'stable':
        # 基准：假设第N年后RE保持常数
        terminal_re = RE_N
        pv_terminal_value = RE_N / ((1+r)^N × (r - g))
    elif re_trend == 'increasing':
        # 乐观：假设第N年后RE继续增长
        terminal_re = RE_N × (1 + g)
        pv_terminal_value = RE_N × (1 + g) / ((1+r)^N × (r - g))

// 4. 计算基准每股价值
V0_基准 = BPS₀ + total_PV_RE + pv_terminal_value

// 5. 计算三种情景的估值（基于不同的终值假设）
# 保守情景：假设第N年后RE=0
V0_保守 = BPS₀ + Σ(PV_RE_t) for t=1 to N

# 基准情景：假设第N年后RE保持常数
V0_基准 = BPS₀ + Σ(PV_RE_t) + PV(RE_终值常数)

# 乐观情景：假设第N年后RE继续增长
V0_乐观 = BPS₀ + Σ(PV_RE_t) + PV(RE_终值增长)

// 注意：终值计算取决于RE趋势分析结果
```

---

## 4. 数据库查询示例

### 4.1 获取最新年报日期

```sql
SELECT report_date
FROM financial_data
WHERE company_code = '000001'
  AND report_type = 'IS'
ORDER BY report_date DESC
LIMIT 1;
```

### 4.2 获取基准年财务数据

```sql
-- 获取净利润
SELECT value_decimal as net_income
FROM financial_data
WHERE company_code = '000001'
  AND subject_code = 'ISF021'
  AND report_type = 'IS'
  AND EXTRACT(YEAR FROM report_date) = 2024
ORDER BY report_date DESC
LIMIT 1;

-- 获取股东权益
SELECT value_decimal as shareholders_equity
FROM financial_data
WHERE company_code = '000001'
  AND subject_code = 'BSE010'
  AND report_type = 'BS'
  AND EXTRACT(YEAR FROM report_date) = 2024
ORDER BY report_date DESC
LIMIT 1;

-- 获取股本
SELECT value_decimal as shares_outstanding
FROM financial_data
WHERE company_code = '000001'
  AND subject_code = 'BSE001'
  AND report_type = 'BS'
  AND EXTRACT(YEAR FROM report_date) = 2024
ORDER BY report_date DESC
LIMIT 1;
```

---

## 5. API接口设计

### 5.1 计算估值接口

**请求参数：**

```json
{
  "stock_code": "000001",
  "cost_of_equity": 0.09,
  "growth_rate": 0.15,
  "terminal_growth_rate": 0.03,
  "projection_years": 5,
  "payout_ratio": 0.30,
  "scenario": "n_years_re_zero"
}
```

**响应数据：**

```json
{
  "company": {
    "stock_code": "000001",
    "stock_name": "平安银行"
  },
  "method": "Residual Income (RI) - N年后RE=0",
  "valuation_date": "2026-01-28",
  "base_report_date": "2024-12-31",
  "parameters": {
    "cost_of_equity": 0.09,
    "growth_rate": 0.15,
    "terminal_growth_rate": 0.03,
    "projection_years": 5,
    "payout_ratio": 0.30,
    "scenario": "n_years_re_zero"
  },
  "inputs": {
    "net_income": 352.45,
    "shareholders_equity": 3580.00,
    "shares_outstanding": 100.00,
    "current_eps": 3.5245,
    "current_bps": 35.80,
    "current_roe": 0.0985
  },
  "valuation": {
    "base_book_value_per_share": 35.80,
    "projected_eps": [4.05, 4.66, 5.36, 6.16, 7.08],
    "projected_dps": [1.22, 1.40, 1.61, 1.85, 2.12],
    "projected_bps": [38.63, 41.89, 45.64, 49.95, 54.91],
    "projected_roe": [0.1131, 0.1206, 0.1280, 0.1350, 0.1421],
    "projected_re": [0.834, 1.032, 1.255, 1.511, 1.799],
    "pv_forecast_re": [0.765, 0.869, 0.969, 1.071, 1.170],
    "total_pv_re": 4.844,
    "intrinsic_value_per_share": 40.644,
    "scenarios": {
      "conservative": {
        "valuation": 34.547,
        "upside_downside": 176.4,
        "rating": "低估"
      },
      "base": {
        "valuation": 40.644,
        "upside_downside": 225.2,
        "rating": "强烈低估"
      },
      "optimistic": {
        "valuation": 46.741,
        "upside_downside": 273.9,
        "rating": "极度低估"
      }
    }
  },
  "current_price": 12.50,
  "upside_downside": 225.2,
  "investment_rating": "强烈低估"
}
```

---

## 6. 前端展示要求

### 6.1 输入区域

**参数假设区域（只增加参数，不改变现有结构）：**

1. **要求回报率输入**：用户可调整（默认9%）
2. **预测期选择**：用户可选择N值（默认5年）
3. **增长率输入**：用户可调整预测期增长率（默认15%）
4. **股利支付率**：用户可调整（默认30%）

**场景选择区域（继续保留现有的三种情景）：**

1. **风险折价（保守）**：基于85%的基准估值
2. **基准价值（Base）**：基于100%的基准估值
3. **乐观溢价（Upside）**：基于115%的基准估值

### 6.2 输出展示

1. **计算表格**：完整展示T0-T5的所有计算过程
   - T0：显示EPS₀、BPS₀、DPS₀、ROE₀（从数据库计算）
   - T1-T5：显示预测的EPS、DPS、BPS、ROCE、RE、折现因子、PV(RE)

2. **关键结果**：
   - Σ PV(RE) = 4.844
   - V₀ = 40.644

3. **图表展示**：
   - ROE趋势图
   - 剩余收益柱状图
   - 价值构成图（BPS₀ + PV(RE)）

### 6.3 预测方法详细解释

在估值页面中，需要向用户清晰解释剩余收益模型的预测方法和计算逻辑，建议采用以下展示方式：

#### 6.3.1 方法概述卡片

**剩余收益模型（RIM）- N年后RE=0场景**

```
核心原理：
每股价值 = 初始每股净资产 + 未来剩余收益的现值

V₀ = BPS₀ + Σ(PV(RE_t))

其中：
- RE_t = EPS_t - r × BPS_{t-1}
- PV(RE_t) = RE_t / (1+r)^t
- 求和从t=1到t=N（N=5）
```

#### 6.3.2 预测步骤说明

**步骤1：基准数据获取（T0）**

从数据库获取最新的年报数据：
- 净利润：352.45万元
- 股东权益：3,580.00万元
- 股本：100.00万元

计算每股数据：
- EPS₀ = 净利润 / 股本 = 3.5245元/股
- BPS₀ = 股东权益 / 股本 = 35.80元/股
- ROE₀ = EPS₀ / BPS₀ = 9.85%

**步骤2：预测期数据预测（T1-T5）**

采用固定增长率法预测未来5年的每股收益：

```
EPS_t = EPS_{t-1} × (1 + 增长率)
DPS_t = EPS_t × 股利支付率
BPS_t = BPS_{t-1} + EPS_t - DPS_t
ROE_t = EPS_t / BPS_{t-1}
```

其中：
- 增长率：15%（可调整）
- 股利支付率：30%（可调整）

**步骤3：剩余收益计算**

计算每期的剩余收益：

```
RE_t = EPS_t - 要求回报率 × BPS_{t-1}
```

剩余收益反映了公司创造的价值超过其资本成本的部分。

**步骤4：折现到现值**

将剩余收益折现到当前时点：

```
PV(RE_t) = RE_t / (1 + 要求回报率)^t
```

**步骤5：计算内在价值**

```
V₀ = BPS₀ + Σ(PV(RE_t))
```

内在价值由两部分组成：
1. 初始每股净资产（BPS₀）：35.80元
2. 未来剩余收益的现值：4.844元

#### 6.3.3 关键参数说明

| 参数 | 说明 | 影响 | 默认值 |
|------|------|------|--------|
| **要求回报率** | 投资者要求的最低收益率 | 越高，估值越低 | 9.00% |
| **增长率** | 预测期EPS增长率 | 越高，估值越高 | 15% |
| **股利支付率** | 净利润中分红的比例 | 越高，BPS增长越慢 | 30% |
| **预测期（N）** | 预测剩余收益的年数 | 越长，估值越高 | 5年 |

#### 6.3.4 情景分析与商业模式对应

**情景计算逻辑（基于RE趋势分析）：**

系统会自动分析预测期（T1-T5）的剩余收益（RE）趋势，根据趋势计算三种情景：

| 情景 | RE趋势 | 终值假设 | 对应情形 | 商业模式 | 适用行业 | 典型公司 |
|------|--------|---------|---------|---------|---------|---------|
| **保守** | RE递减 | 第N年后RE=0 | 情形1：N年后RE=0 | 成熟期/衰退期 | 传统制造业、公用事业、银行业 | 浦发银行、京东方A、宝钢股份 |
| **基准** | RE稳定 | 第N年后RE=常数 | 情形2：N年后RE为常数 | 稳定增长期 | 消费品、医药、知名品牌 | 茅台、可口可乐、恒瑞医药 |
| **乐观** | RE递增 | 第N年后RE继续增长 | 情形3：N年后RE持续增长 | 高成长期 | 科技公司、新能源、创新药 | 比亚迪、宁德时代、药明康德 |

**RE趋势判断标准：**

```python
# 分析RE趋势
re_sequence = [RE₁, RE₂, RE₃, RE₄, RE₅]

# 计算趋势斜率
re_trend_slope = linear_regression(re_sequence)

# 判断趋势
if re_trend_slope < -threshold:
    re_trend = 'decreasing'  # RE递减
elif abs(re_trend_slope) <= threshold:
    re_trend = 'stable'       # RE稳定
else:
    re_trend = 'increasing'  # RE递增
```

**情景计算公式：**

**保守情景（RE递减）：**
```
假设：第N年后剩余收益归零（RE_N+1 = 0）
估值 = BPS₀ + Σ(PV(RE_t)) for t=1 to N
终值 = 0
```

**基准情景（RE稳定）：**
```
假设：第N年后剩余收益保持常数（RE_N+1 = RE_N）
估值 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值常数)
终值 = RE_N / (r - g)
```

**乐观情景（RE递增）：**
```
假设：第N年后剩余收益继续增长（RE_N+1 = RE_N × (1+g)）
估值 = BPS₀ + Σ(PV(RE_t)) + PV(RE_终值增长)
终值 = RE_N × (1+g) / (r - g)
```

**情景详细说明：**

**保守情景（情形1：N年后RE=0）**

```
商业含义：成熟期/衰退期公司

特征：
- 市场饱和，增长空间有限
- ROE逐渐下降到等于股权成本（r）
- 剩余收益在第N年后归零（RE = 0）
- 公司进入维持期，无法扩大股东价值
- 需要高风险折价（估值×85%）

适用公司：
  ✓ 传统制造业（钢铁、水泥、纺织）
  ✓ 公用事业（电力、水务、燃气）
  ✓ 传统银行业务（利差收窄）
  ✓ 零售连锁（市场饱和）
  ✓ 电信运营商（成熟期）

财务特征：
  T0-TN: ROE 从高位下降 → 接近 r
  T+N以后: RE = 0 (ROE = r)
  增长动力: 市场饱和 + 竞争加剧
```

**基准情景（情形2：N年后RE为常数）**

```
商业含义：稳定增长公司

特征：
- 拥有品牌护城河或技术壁垒
- ROE稳定在股权成本之上
- 剩余收益在第N年后保持恒定（RE = 常数 > 0）
- 公司能维持超额收益
- 估值倍数基准（×100%）

适用公司：
  ✓ 消费品（知名品牌、重复消费）
  ✓ 医药行业（创新药企、专利壁垒）
  ✓ 科技公司（成熟期的SaaS）
  ✓ 食品饮料（高端品牌、提价能力）
  ✓ 金融服务业（券商、保险）

财务特征：
  T0-TN: ROE 保持高位 → 稳定
  T+N以后: RE = 常数 > 0 (ROE > r)
  增长动力: 品牌效应 + 垄断地位 + 重复消费
```

**乐观情景（情形3：N年后RE持续增长）**

```
商业含义：高成长公司

特征：
- 拥有技术创新或商业模式创新
- ROE持续高于股权成本
- 剩余收益在第N年后继续增长（RE持续增加）
- 公司具备持续创造超额价值的能力
- 估值倍数最高（×115%）

适用公司：
  ✓ 新兴科技公司（SaaS、AI、云计算）
  ✓ 高端制造业（半导体、新能源）
  ✓ 生物医药（创新药研发）
  ✓ 互联网平台（高成长期）
  ✓ 新能源汽车（技术突破+市场扩张）

财务特征：
  T0-TN: ROE 持续提升
  T+N以后: RE 继续增长 (RE_{t+1} = RE_t × (1+g))
  增长动力: 技术创新 + 网络效应 + 规模经济
```

**情景选择指南：**

选择保守情景时：
- ✓ 市场竞争激烈，利润率持续下降
- ✓ 公司缺乏核心竞争力
- ✓ 行业进入衰退期
- ✓ 需要高风险折价保护

选择基准情景时：
- ✓ 公司有稳定的护城河
- ✓ 历史ROE持续稳定
- ✓ 行业成熟，增长平稳
- ✓ 适合长期持有

选择乐观情景时：
- ✓ 技术创新或商业模式创新
- ✓ 高增长潜力，ROE持续提升
- ✓ 拥有网络效应或规模经济
- ✓ 适合成长型投资

#### 6.3.5 模型适用性说明

**适用场景：**
✓ ROE持续高于要求回报率的公司
✓ 账面价值较为稳定的公司
✓ 高增长但分红率较低的公司
✓ 估值需要基于会计数据的公司

**不适用场景：**
✗ 周期性较强的公司（波动大）
✗ ROE低于要求回报率的公司（剩余收益为负）
✗ 账面价值失真的公司（如金融企业特殊处理）
✗ 快速扩张期的初创企业

#### 6.3.5 风险提示

⚠️ **预测假设风险**
- 模型假设未来5年ROE持续高于要求回报率
- 增长率和股利支付率的假设对估值影响较大
- 实际经营环境可能与预测存在偏差

⚠️ **模型局限**
- N年后RE=0的假设可能过于乐观或悲观
- 未考虑市场情绪和行业竞争变化
- 会计政策变更可能影响账面价值

---

## 7. 重要说明

1. **数据存储**：只存储基础财务数据（净利润、股东权益、股本），所有每股数据（EPS、BPS、DPS）和计算字段（ROE、RE）都是实时计算得出

2. **基准年选择**：自动查询最新的年报日期作为基准年（T0）

3. **预测数据**：T1-T5的EPS、DPS、BPS是预测值，不存储在数据库中

4. **计算字段**：ROE、RE、折现因子、PV(RE)等都是计算字段，不需要存储

5. **N年后RE=0场景**：此场景不需要计算终值，只计算预测期的剩余收益现值

6. **默认预测期**：N默认为5年

---

## 8. 示例计算

假设平安银行的数据：

**输入数据（T0）：**
- BPS₀ = 35.80元
- r = 9.00%
- N = 5
- growth_rate = 15%
- payout_ratio = 30%

**计算过程：**

| t | EPS | DPS | BPS_{t-1} | ROE | RE | (1+r)^t | PV(RE) |
|---|-----|-----|-----------|------|----|---------|--------|
| 1 | 4.05 | 1.22 | 35.80 | 11.31% | 0.834 | 1.09 | 0.765 |
| 2 | 4.66 | 1.40 | 38.63 | 12.06% | 1.032 | 1.1881 | 0.869 |
| 3 | 5.36 | 1.61 | 41.89 | 12.80% | 1.255 | 1.2950 | 0.969 |
| 4 | 6.16 | 1.85 | 45.64 | 13.50% | 1.511 | 1.4116 | 1.071 |
| 5 | 7.08 | 2.12 | 49.95 | 14.21% | 1.799 | 1.5386 | 1.170 |

**最终结果：**
- Σ PV(RE) = 0.765 + 0.869 + 0.969 + 1.071 + 1.170 = 4.844
- V₀ = 35.80 + 4.844 = **40.644元**

---

## 附录：ResidualIncomeService代码实现

ResidualIncomeService位于 `backend/valuation/residual_income.py`，实现了完整的剩余收益估值逻辑。

### 后端更新建议

**需要修改的文件：** `backend/valuation/residual_income.py`

**修改内容：**

1. **添加RE趋势分析方法**

```python
def _analyze_re_trend(self, re_sequence: List[Decimal]) -> str:
    """
    分析剩余收益趋势

    Args:
        re_sequence: RE序列 [RE₁, RE₂, ..., RE_N]

    Returns:
        'decreasing' | 'stable' | 'increasing'
    """
    if len(re_sequence) < 2:
        return 'stable'

    # 计算趋势斜率
    n = len(re_sequence)
    x_values = list(range(1, n + 1))

    # 简单线性回归计算斜率
    sum_x = sum(x_values)
    sum_y = sum(re_sequence)
    sum_xy = sum(x * y for x, y in zip(x_values, re_sequence))
    sum_x2 = sum(x ** 2 for x in x_values)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

    # 计算平均RE
    avg_re = sum_y / n

    # 判断趋势（阈值：平均RE的5%）
    threshold = avg_re * Decimal('0.05')

    if slope < -threshold:
        return 'decreasing'
    elif abs(slope) <= threshold:
        return 'stable'
    else:
        return 'increasing'
```

2. **在 `_calculate_ri_valuation` 方法中添加基于RE趋势的情景计算**

```python
# 6. 计算每股内在价值（基准）
intrinsic_value_per_share = current_bps + pv_projected_ri + pv_terminal_value

# 7. 分析RE趋势
re_trend = self._analyze_re_trend(projected_ri)

# 8. 计算三种情景的估值（基于RE趋势）
scenarios = {}

# 保守情景：假设第N年后RE=0
pv_terminal_conservative = Decimal('0')
valuation_conservative = current_bps + pv_projected_ri + pv_terminal_conservative

# 基准情景：假设第N年后RE保持常数
if re_trend == 'stable' or re_trend == 'increasing':
    # 使用最后一个预测年的RE作为终值
    terminal_re = projected_ri[-1]
    pv_terminal_base = self._calculate_terminal_value(
        terminal_re,
        params['cost_of_equity'],
        params['projection_years'],
        params['terminal_growth_rate']
    )
else:
    # RE递减时，基准情景也假设终值较小
    terminal_re = projected_ri[-1] * Decimal('0.5')
    pv_terminal_base = self._calculate_terminal_value(
        terminal_re,
        params['cost_of_equity'],
        params['projection_years'],
        params['terminal_growth_rate']
    )

valuation_base = current_bps + pv_projected_ri + pv_terminal_base

# 乐观情景：假设第N年后RE继续增长
if re_trend == 'increasing':
    # 使用增长后的RE作为终值
    terminal_re = projected_ri[-1] * (Decimal('1') + params['growth_rate'])
    pv_terminal_optimistic = self._calculate_terminal_value(
        terminal_re,
        params['cost_of_equity'],
        params['projection_years'],
        params['terminal_growth_rate']
    )
elif re_trend == 'stable':
    # RE稳定时，乐观情景假设适度增长
    terminal_re = projected_ri[-1] * (Decimal('1') + params['terminal_growth_rate'])
    pv_terminal_optimistic = self._calculate_terminal_value(
        terminal_re,
        params['cost_of_equity'],
        params['projection_years'],
        params['terminal_growth_rate']
    )
else:
    # RE递减时，乐观情景假设终值保持不变
    terminal_re = projected_ri[-1]
    pv_terminal_optimistic = self._calculate_terminal_value(
        terminal_re,
        params['cost_of_equity'],
        params['projection_years'],
        params['terminal_growth_rate']
    )

valuation_optimistic = current_bps + pv_projected_ri + pv_terminal_optimistic

# 构建情景数据
scenarios = {
    'conservative': {
        'valuation': float(valuation_conservative),
        'upside_downside': None,
        'rating': None,
        're_trend': re_trend,
        'terminal_assumption': 'RE_N+1 = 0'
    },
    'base': {
        'valuation': float(valuation_base),
        'upside_downside': None,
        'rating': None,
        're_trend': re_trend,
        'terminal_assumption': 'RE_N+1 = RE_N'
    },
    'optimistic': {
        'valuation': float(valuation_optimistic),
        'upside_downside': None,
        'rating': None,
        're_trend': re_trend,
        'terminal_assumption': 'RE_N+1 = RE_N × (1+g)'
    }
}

# 9. 为每种情景计算涨跌幅和评级
current_price = company.current_price or Decimal('0')
if current_price > 0:
    for scenario_name, scenario_data in scenarios.items():
        scenario_valuation = Decimal(str(scenario_data['valuation']))
        upside_downside = (
            ((scenario_valuation - current_price) / current_price * Decimal('100'))
            .quantize(Decimal('0.01'))
        )
        scenario_data['upside_downside'] = float(upside_downside)
        scenario_data['rating'] = self._generate_investment_rating(upside_downside)

# 10. 更新返回数据
return {
    # ... 现有字段 ...
    "valuation": {
        # ... 现有字段 ...
        "scenarios": scenarios,
        "re_trend": re_trend  # 新增：RE趋势
    },
    # ... 现有字段 ...
}
```

3. **添加终值计算辅助方法**

```python
def _calculate_terminal_value(
    self,
    terminal_re: Decimal,
    cost_of_equity: float,
    projection_years: int,
    terminal_growth_rate: float
) -> Decimal:
    """
    计算终值的现值

    Args:
        terminal_re: 第N年的剩余收益
        cost_of_equity: 要求回报率
        projection_years: 预测年数
        terminal_growth_rate: 永续增长率

    Returns:
        终值的现值
    """
    r = Decimal(str(cost_of_equity))
    g = Decimal(str(terminal_growth_rate))
    n = projection_years

    # 永续增长模型：TV = RE_N × (1+g) / (r-g)
    if r <= g:
        # 如果r <= g，返回0（避免负值或无限大）
        return Decimal('0')

    terminal_value = terminal_re * (Decimal('1') + g) / (r - g)

    # 折现到当前时点：PV = TV / (1+r)^N
    discount_factor = (Decimal('1') + r) ** n
    pv_terminal_value = terminal_value / discount_factor

    return pv_terminal_value
```

2. **在 `DEFAULT_PARAMS` 中确认默认值**

```python
DEFAULT_PARAMS = {
    "cost_of_equity": 0.09,        # 股权成本率（建议改为0.09以匹配文档）
    "growth_rate": 0.15,           # 预测期增长率
    "terminal_growth_rate": 0.03,  # 永续增长率
    "projection_years": 5,         # 预测年数（默认改为5）
    "payout_ratio": 0.30,          # 股利支付率
    "scenario": "n_years_re_zero" # 新增：默认场景
}
```

3. **验证科目编码映射**

确保 `SUBJECT_CODES` 包含所有需要的科目：

```python
SUBJECT_CODES = {
    # 利润表科目
    'revenue': ['ISI001'],              # 营业收入
    'net_income': ['ISF021'],           # 净利润

    # 资产负债表科目
    'total_assets': ['BSA121'],         # 资产总计
    'total_liabilities': ['BSL112'],    # 负债合计
    'shareholders_equity': ['BSE010'],  # 归属于母公司所有者权益合计
    'shares_outstanding': ['BSE001'],   # 实收资本（或股本）
}
```

**核心方法：**

1. `valuate()`: 主估值方法
2. `_get_base_financials()`: 从数据库获取基准财务数据
3. `_project_per_share_data()`: 预测每股数据
4. `_calculate_projected_roe_and_ri()`: 计算预测ROE和剩余收益
5. `_calculate_pv_projected_ri()`: 计算剩余收益现值

**科目编码映射（SUBJECT_CODES）：**

```python
SUBJECT_CODES = {
    # 利润表科目
    'revenue': ['ISI001'],              # 营业收入
    'net_income': ['ISF021'],           # 净利润

    # 资产负债表科目
    'total_assets': ['BSA121'],         # 资产总计
    'total_liabilities': ['BSL112'],    # 负债合计
    'shareholders_equity': ['BSE010'],  # 归属于母公司所有者权益合计
    'shares_outstanding': ['BSE001'],   # 实收资本（或股本）
}
```

---

**文档版本：** v1.0  
**最后更新：** 2026-02-07  
**作者：** AI Investor Team