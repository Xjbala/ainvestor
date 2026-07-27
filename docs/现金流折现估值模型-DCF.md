# 现金流折现估值模型（DCF）

## 1. 模型概述

### 1.1 核心原理

现金流折现模型（Discounted Cash Flow, DCF）是企业估值中最经典和广泛使用的方法之一，其核心思想是：

- **企业价值 = 未来所有自由现金流的现值之和**
- **股权价值 = 企业价值 - 净债务**
- **每股内在价值 = 股权价值 / 总股本**

DCF模型基于以下基本假设：
1. 企业在未来能够持续产生自由现金流
2. 可以合理预测未来现金流的增长模式
3. 投资者要求的风险回报率（WACC）是合理的
4. 企业最终会进入稳定增长阶段（永续增长）

### 1.2 关键公式

**自由现金流计算（新公式）：**

```
FCF = 税后利润 + 折旧和摊销 - 营运资本增加 - 资本支出
```

其中：
- 税后利润 = 营业利润 - 所得税费用
- 折旧和摊销 = 减值损失（累计折旧已忽略）
- 营运资本增加 = 货币资金增加 + 存货增加 + 经营性应收增加 + 待摊费用增加 - 经营性应付增加
  - 货币资金增加 = 货币资金（期末-期初）
  - 存货增加 = 存货（期末-期初）
  - 经营性应收增加 = 应收账款（期末-期初）+ 应收票据（期末-期初）+ 预付账款（期末-期初）+ 其他应收款（期末-期初）+ 待摊费用（期末-期初）
  - 待摊费用增加 = 待摊费用（期末-期初）
  - 经营性应付增加 = 应付账款（期末-期初）+ 预收账款（期末-期初）+ 应付票据（期末-期初）+ 应付职工薪酬（期末-期初）+ 应交税费（期末-期初）+ 其他应付款（期末-期初）
- 资本支出 = 购建固定资产、无形资产等支付的现金 + 取得子公司及其他营业单位支付的现金净额

**说明：**
- 如果公司只有一年财务数据（如刚上市），期初值设为0
- 累计折旧科目在数据库中未配置，已忽略（仅使用减值损失）
- 应付福利费和预提费用科目在数据库中未配置，已忽略

**企业价值计算：**

```
EV = Σ(PV(FCF_t)) for t=1 to N + PV(TV)
```

其中：
- EV：企业价值（Enterprise Value）
- PV(FCF_t) = FCF_t / (1+WACC)^t：第t年自由现金流的现值
- TV：终值（Terminal Value），第N年后永续阶段的现金流现值
- N：预测期年数（通常5年）
- WACC：加权平均资本成本（折现率）

**终值计算（永续增长模型）：**

```
TV = FCF_N × (1 + g) / (WACC - g)
```

其中：
- FCF_N：第N年的自由现金流
- g：永续增长率
- WACC：加权平均资本成本

**股权价值计算：**

```
股权价值 = 企业价值 - 净债务
净债务 = 有息债务 - 现金及现金等价物
```

**每股内在价值计算：**

```
每股内在价值 = 股权价值 / 总股本
```

**情景估值计算（基于FCF趋势分析）：**

```
# 步骤1：计算预测期（T1-TN）的FCF序列
fcf_sequence = [FCF₁, FCF₂, ..., FCF_N]

# 步骤2：分析FCF趋势
fcf_trend = analyze_fcf_trend(fcf_sequence)

# 步骤3：根据趋势计算三种情景估值
if fcf_trend == 'decreasing':
    # 保守情景：FCF递减，使用较低的永续增长率
    V₀_保守 = Σ(PV(FCF_t)) + PV(TV_低增长)
    V₀_基准 = Σ(PV(FCF_t)) + PV(TV_基准)
    V₀_乐观 = Σ(PV(FCF_t)) + PV(TV_高增长)
elif fcf_trend == 'stable':
    # 基准情景：FCF稳定，使用基准永续增长率
    V₀_保守 = Σ(PV(FCF_t)) + PV(TV_低增长)
    V₀_基准 = Σ(PV(FCF_t)) + PV(TV_基准)
    V₀_乐观 = Σ(PV(FCF_t)) + PV(TV_高增长)
elif fcf_trend == 'increasing':
    # 乐观情景：FCF递增，使用较高的永续增长率
    V₀_保守 = Σ(PV(FCF_t)) + PV(TV_低增长)
    V₀_基准 = Σ(PV(FCF_t)) + PV(TV_基准)
    V₀_乐观 = Σ(PV(FCF_t)) + PV(TV_高增长)
```

**情景说明：**

| 页面显示 | FCF趋势 | 永续增长率假设 | 商业含义 |
|---------|--------|---------------|---------|
| **保守** | FCF递减 | 1-2% | 成熟期/衰退期公司，现金流增长放缓 |
| **基准** | FCF稳定 | 3% | 稳定增长公司，现金流保持平稳 |
| **乐观** | FCF递增 | 4-5% | 高成长公司，现金流持续增长 |

**核心优势：**
- 直接关注企业创造现金的能力
- 不受会计政策影响（现金流是客观的）
- 适用于现金流稳定或可预测的企业
- 考虑了货币的时间价值

---

## 2. 数据存储模式（核心）

### 2.1 数据库存储结构

财务数据存储在 `financial_data` 表中，采用**科目编码+报告期**的存储方式：

```
表名: financial_data
关键字段:
- company_code: 股票代码 (如 "000001")
- subject_code: 科目编码 (如 "CFO020" 表示经营活动产生的现金流量净额)
- report_date: 报告日期 (如 "2024-12-31")
- report_type: 报表类型 (BS/IS/CF/OE)
- value_decimal: 数值 (单位：万元)
```

### 2.2 科目编码映射

**DCFValuationService使用的科目编码：**

| 财务指标 | 科目编码 | 报表类型 | 说明 |
|---------|---------|---------|------|
| **基础数据（存储在数据库）** |
| 营业收入 | ISI001 | IS | 利润表科目 |
| 营业利润 | ISF016 | IS | 利润表科目 |
| 净利润 | ISF021 | IS | 利润表科目 |
| 资产总计 | BSA121 | BS | 资产负债表科目 |
| 负债合计 | BSL112 | BS | 资产负债表科目 |
| 归属于母公司所有者权益合计 | BSE010 | BS | 资产负债表科目 |
| 实收资本（或股本） | BSE001 | BS | 资产负债表科目 |
| **利润表科目（新FCF公式）** |
| 所得税费用 | ISF020 | IS | 利润表科目 |
| 信用减值损失 | ISF014 | IS | 利润表科目（减值准备） |
| **资产负债表科目（新FCF公式）** |
| 存货 | BSA015 | BS | 资产负债表科目 |
| 应收账款 | BSA007 | BS | 资产负债表科目 |
| 应收票据 | BSA006 | BS | 资产负债表科目 |
| 预付款项 | BSA009 | BS | 资产负债表科目（预付账款/待摊费用） |
| 其他应收款 | BSA013 | BS | 资产负债表科目 |
| 应付账款 | BSL007 | BS | 资产负债表科目 |
| 预收款项 | BSL008 | BS | 资产负债表科目 |
| 合同负债 | BSL009 | BS | 资产负债表科目 |
| 应付票据 | BSL006 | BS | 资产负债表科目 |
| 应付职工薪酬 | BSL014 | BS | 资产负债表科目 |
| 应交税费 | BSL015 | BS | 资产负债表科目 |
| 其他应付款 | BSL016 | BS | 资产负债表科目 |
| **现金流量表科目** |
| 经营活动产生的现金流量净额 | CFO020 | CF | 现金流量表科目 |
| 购建固定资产、无形资产和其他长期资产支付的现金 | CFIV007 | CF | 现金流量表科目 |
| 取得子公司及其他营业单位支付的现金净额 | CFIV009 | CF | 现金流量表科目 |
| **债务科目** |
| 短期借款 | BSL001 | BS | 资产负债表科目 |
| 向中央银行借款 | BSL002 | BS | 资产负债表科目 |
| 拆入资金 | BSL003 | BS | 资产负债表科目 |
| 长期借款 | BSL102 | BS | 资产负债表科目 |
| 应付债券 | BSL103 | BS | 资产负债表科目 |
| 货币资金 | BSA001 | BS | 资产负债表科目 |
| 结算备付金 | BSA002 | BS | 资产负债表科目 |
| 拆出资金 | BSA003 | BS | 资产负债表科目 |
| **计算字段（不存储，实时计算）** |
| 税后利润 | - | - | = 营业利润 - 所得税费用 |
| 折旧和摊销 | - | - | = 减值损失（累计折旧已忽略） |
| 营运资本增加 | - | - | = 货币资金增加 + 存货增加 + 经营性应收增加 - 经营性应付增加 |
| 自由现金流 | - | - | = 税后利润 + 折旧和摊销 - 营运资本增加 - 资本支出 |
| 净债务 | - | - | = 有息债务 - 现金及现金等价物 |
| 企业价值 | - | - | = 预测期FCF现值 + 终值现值 |
| 股权价值 | - | - | = 企业价值 - 净债务 |
| 每股内在价值 | - | - | = 股权价值 / 总股本 |

### 2.3 数据获取流程

**步骤1：确定基准报告期**

```python
# 查询最新的年报日期
report_date = SELECT report_date FROM financial_data
              WHERE company_code = '000001'
                AND report_type = 'CF'
              ORDER BY report_date DESC LIMIT 1
# 结果：2024-12-31
base_year = 2024
```

**步骤2：获取基准财务数据（T0）**

```python
# 从数据库获取基准年的基础数据
operating_income = SELECT value_decimal FROM financial_data
                    WHERE company_code = '000001'
                      AND subject_code = 'ISF016'
                      AND YEAR(report_date) = 2024

tax_expense = SELECT value_decimal FROM financial_data
              WHERE company_code = '000001'
                AND subject_code = 'ISF020'
                AND YEAR(report_date) = 2024

impairment_loss = SELECT value_decimal FROM financial_data
                 WHERE company_code = '000001'
                   AND subject_code = 'ISF014'
                   AND YEAR(report_date) = 2024

capital_expenditure = SELECT value_decimal FROM financial_data
                      WHERE company_code = '000001'
                        AND subject_code = 'CFIV007'
                        AND YEAR(report_date) = 2024

subsidiary_investment = SELECT value_decimal FROM financial_data
                        WHERE company_code = '000001'
                          AND subject_code = 'CFIV009'
                          AND YEAR(report_date) = 2024

# 获取资产负债表期初期末变化量（计算营运资本增加）
# 期末值（基准年）
balance_sheet_end = {}
for subject_code in ['BSA001', 'BSA015', 'BSA007', 'BSA006', 'BSA009', 'BSA013', 
                     'BSL007', 'BSL008', 'BSL009', 'BSL006', 'BSL014', 'BSL015', 'BSL016']:
    value = SELECT value_decimal FROM financial_data
            WHERE company_code = '000001'
              AND subject_code = subject_code
              AND YEAR(report_date) = 2024
    balance_sheet_end[subject_code] = value or 0

# 期初值（上一年），如果不存在则为0
balance_sheet_start = {}
for subject_code in balance_sheet_end.keys():
    value = SELECT value_decimal FROM financial_data
            WHERE company_code = '000001'
              AND subject_code = subject_code
              AND YEAR(report_date) = 2023
    balance_sheet_start[subject_code] = value or 0

# 计算自由现金流（新公式）
# 1. 税后利润 = 营业利润 - 所得税费用
after_tax_profit = operating_income - tax_expense

# 2. 折旧和摊销 = 减值损失（累计折旧已忽略）
depreciation_amortization = impairment_loss

# 3. 营运资本增加
cash_change = (BSA001_end - BSA001_start) + (BSA002_end - BSA002_start) + (BSA003_end - BSA003_start)
inventory_change = BSA015_end - BSA015_start
receivables_change = (BSA007_end - BSA007_start) + (BSA006_end - BSA006_start) + (BSA009_end - BSA009_start) + (BSA013_end - BSA013_start)
payables_change = (BSL007_end - BSL007_start) + (BSL008_end - BSL008_start) + (BSL009_end - BSL009_start) + (BSL006_end - BSL006_start) + (BSL014_end - BSL014_start) + (BSL015_end - BSL015_start) + (BSL016_end - BSL016_start)
working_capital_increase = cash_change + inventory_change + receivables_change - payables_change

# 4. 资本支出
total_capital_expenditure = capital_expenditure + subsidiary_investment

# 5. 自由现金流
base_fcf = after_tax_profit + depreciation_amortization - working_capital_increase - total_capital_expenditure
```

**步骤3：获取债务数据**

```python
# 获取有息债务
short_term_debt = SELECT SUM(value_decimal) FROM financial_data
                  WHERE company_code = '000001'
                    AND subject_code IN ('BSL001', 'BSL002', 'BSL003')
                    AND YEAR(report_date) = 2024

long_term_debt = SELECT SUM(value_decimal) FROM financial_data
                 WHERE company_code = '000001'
                   AND subject_code IN ('BSL102', 'BSL103')
                   AND YEAR(report_date) = 2024

total_debt = short_term_debt + long_term_debt

# 获取现金及现金等价物
cash = SELECT SUM(value_decimal) FROM financial_data
       WHERE company_code = '000001'
         AND subject_code IN ('BSA001', 'BSA002', 'BSA003')
         AND YEAR(report_date) = 2024

# 计算净债务
net_debt = total_debt - cash
```

**步骤4：预测T1-N的数据**

```python
# 使用增长率预测未来N年的自由现金流
for t in 1 to N:
    projected_fcf[t] = projected_fcf[t-1] × (1 + growth_rate)
```

---

## 3. 计算流程（完整版）

### 3.1 输入参数

| 参数 | 说明 | 数据来源 | 默认值 |
|------|------|----------|--------|
| **stock_code** | 股票代码 | 用户输入 | - |
| **base_year** | 基准年 | 自动查询最新年报 | 2024 |
| **growth_rate** | 预测期增长率 | 默认/用户输入 | 15% |
| **terminal_growth_rate** | 永续增长率 | 默认/用户输入 | 3% |
| **discount_rate** | 折现率（WACC） | 默认/用户输入 | 10% |
| **tax_rate** | 企业所得税率 | 默认/用户输入 | 25% |
| **projection_years** | 预测年数（N） | 默认/用户输入 | 5 |

### 3.2 从数据库获取的基准数据（T0）

| 财务科目 | 科目编码 | 获取SQL | 单位 |
|---------|---------|---------|------|
| 经营活动产生的现金流量净额 | CFO020 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='CFO020' AND YEAR(report_date)=base_year` | 万元 |
| 资本性支出 | CFIV007 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='CFIV007' AND YEAR(report_date)=base_year` | 万元 |
| 有息债务 | BSL001, BSL002, BSL003, BSL102, BSL103 | `SELECT SUM(value_decimal) FROM financial_data WHERE company_code=? AND subject_code IN (...) AND YEAR(report_date)=base_year` | 万元 |
| 现金及现金等价物 | BSA001, BSA002, BSA003 | `SELECT SUM(value_decimal) FROM financial_data WHERE company_code=? AND subject_code IN (...) AND YEAR(report_date)=base_year` | 万元 |
| 股本 | BSE001 | `SELECT value_decimal FROM financial_data WHERE company_code=? AND subject_code='BSE001' AND YEAR(report_date)=base_year` | 万元 |

### 3.3 T0计算字段

| 指标 | 计算公式 | 示例值 |
|------|----------|--------|
| 税后利润 | 营业利润 - 所得税费用 | 300万元 |
| 折旧和摊销 | 减值损失 | 20万元 |
| 营运资本增加 | 货币资金增加 + 存货增加 + 经营性应收增加 - 经营性应付增加 | 50万元 |
| 资本支出 | 购建固定资产等 + 子公司投资现金 | 70万元 |
| 自由现金流 | 税后利润 + 折旧和摊销 - 营运资本增加 - 资本支出 | 200万元 |
| 净债务 | 有息债务 - 现金及现金等价物 | 200万元 |

### 3.4 T1-N预测和计算流程

```
for t in 1 to N:
    # 1. 预测自由现金流（按增长率增长）
    FCF_t = FCF_{t-1} × (1 + growth_rate)

    # 2. 计算折现因子
    discount_factor = (1 + WACC)^t

    # 3. 计算自由现金流现值
    PV_FCF_t = FCF_t / discount_factor
```

### 3.5 终值计算

```
# 1. 计算终值
Terminal_FCF = FCF_N × (1 + terminal_growth_rate)
Terminal_Value = Terminal_FCF / (WACC - terminal_growth_rate)

# 2. 计算终值的现值
PV_Terminal_Value = Terminal_Value / (1 + WACC)^N
```

### 3.6 汇总计算

```
// 1. 计算预测期自由现金流现值总和
Total_PV_FCF = Σ(PV_FCF_t) for t=1 to N

// 2. 计算企业价值
Enterprise_Value = Total_PV_FCF + PV_Terminal_Value

// 3. 计算股权价值
Equity_Value = Enterprise_Value - Net_Debt

// 4. 计算每股内在价值
Intrinsic_Value_Per_Share = Equity_Value / Shares_Outstanding
```

---

## 4. 数据库查询示例

### 4.1 获取最新年报日期

```sql
SELECT report_date
FROM financial_data
WHERE company_code = '000001'
  AND report_type = 'CF'
ORDER BY report_date DESC
LIMIT 1;
```

### 4.2 获取基准年现金流量数据

```sql
-- 获取经营活动产生的现金流量净额
SELECT value_decimal as operating_cash_flow
FROM financial_data
WHERE company_code = '000001'
  AND subject_code = 'CFO020'
  AND report_type = 'CF'
  AND EXTRACT(YEAR FROM report_date) = 2024
ORDER BY report_date DESC
LIMIT 1;

-- 获取资本性支出
SELECT value_decimal as capital_expenditure
FROM financial_data
WHERE company_code = '000001'
  AND subject_code = 'CFIV007'
  AND report_type = 'CF'
  AND EXTRACT(YEAR FROM report_date) = 2024
ORDER BY report_date DESC
LIMIT 1;
```

### 4.3 获取债务数据

```sql
-- 获取有息债务
SELECT SUM(value_decimal) as total_debt
FROM financial_data
WHERE company_code = '000001'
  AND subject_code IN ('BSL001', 'BSL002', 'BSL003', 'BSL102', 'BSL103')
  AND report_type = 'BS'
  AND EXTRACT(YEAR FROM report_date) = 2024;

-- 获取现金及现金等价物
SELECT SUM(value_decimal) as cash
FROM financial_data
WHERE company_code = '000001'
  AND subject_code IN ('BSA001', 'BSA002', 'BSA003')
  AND report_type = 'BS'
  AND EXTRACT(YEAR FROM report_date) = 2024;
```

---

## 5. API接口设计

### 5.1 计算估值接口

**请求参数：**

```json
{
  "stock_code": "000001",
  "growth_rate": 0.15,
  "terminal_growth_rate": 0.03,
  "discount_rate": 0.10,
  "tax_rate": 0.25,
  "projection_years": 5
}
```

**响应数据：**

```json
{
  "company": {
    "stock_code": "000001",
    "stock_name": "平安银行"
  },
  "method": "Discounted Cash Flow (DCF)",
  "valuation_date": "2026-01-28",
  "base_report_date": "2024-12-31",
  "parameters": {
    "growth_rate": 0.15,
    "terminal_growth_rate": 0.03,
    "discount_rate": 0.10,
    "tax_rate": 0.25,
    "projection_years": 5,
    "shares_outstanding": 100.00
  },
  "inputs": {
    "operating_cash_flow": 800.00,
    "capital_expenditure": 300.00,
    "base_fcf": 500.00,
    "net_debt": 200.00
  },
  "valuation": {
    "pv_projected_fcf": 1800.00,
    "terminal_value": 5000.00,
    "pv_terminal_value": 3104.00,
    "enterprise_value": 4904.00,
    "equity_value": 4704.00,
    "intrinsic_value_per_share": 47.04,
    "calculation_detail": {
      "base_fcf": 500.00,
      "projected_fcf": [575, 661, 760, 874, 1005],
      "pv_projected_fcf_detail": [523, 546, 571, 597, 624],
      "terminal_fcf": 1035,
      "terminal_value": 14786,
      "discount_factors": [0.909, 0.826, 0.751, 0.683, 0.621]
    }
  },
  "current_price": 12.50,
  "upside_downside": 276.3,
  "investment_rating": "STRONG_BUY"
}
```

---

## 6. 前端展示要求

### 6.1 输入区域

**参数假设区域：**

1. **增长率输入**：用户可调整（默认15%）
2. **永续增长率输入**：用户可调整（默认3%）
3. **折现率输入**：用户可调整（默认10%）
4. **预测期选择**：用户可选择N值（默认5年）

**场景选择区域：**

1. **保守**：基于较低的永续增长率（1-2%）
2. **基准**：基于基准永续增长率（3%）
3. **乐观**：基于较高的永续增长率（4-5%）

### 6.2 输出展示

1. **计算表格**：完整展示T0-T5的所有计算过程
   - T0：显示基准自由现金流、净债务
   - T1-T5：显示预测的FCF、折现因子、PV(FCF)

2. **关键结果**：
   - Σ PV(FCF) = 2861
   - 企业价值 = 5965
   - 股权价值 = 5765
   - 每股内在价值 = 57.65

3. **图表展示**：
   - FCF趋势图
   - 价值构成图（预测期现值 + 终值现值）

### 6.3 预测方法详细解释

在估值页面中，需要向用户清晰解释DCF模型的预测方法和计算逻辑。

#### 6.3.1 方法概述卡片

**现金流折现模型（DCF）**

```
核心原理：
企业价值 = 预测期自由现金流现值 + 终值现值
股权价值 = 企业价值 - 净债务
每股内在价值 = 股权价值 / 总股本

其中：
- FCF = 经营活动产生的现金流量净额 - 资本性支出
- PV(FCF_t) = FCF_t / (1+WACC)^t
- TV = FCF_N × (1+g) / (WACC-g)
```

#### 6.3.2 预测步骤说明

**步骤1：基准数据获取（T0）**

从数据库获取最新的年报数据：
- 经营活动产生的现金流量净额：800万元
- 资本性支出：300万元
- 有息债务：500万元
- 现金及现金等价物：300万元

计算基准数据：
- 自由现金流 = 800 - 300 = 500万元
- 净债务 = 500 - 300 = 200万元

**步骤2：预测期数据预测（T1-T5）**

采用固定增长率法预测未来5年的自由现金流：

```
FCF_t = FCF_{t-1} × (1 + 增长率)
```

其中：
- 增长率：15%（可调整）

**步骤3：折现到现值**

将预测的自由现金流折现到当前时点：

```
PV(FCF_t) = FCF_t / (1 + WACC)^t
```

其中：
- WACC：加权平均资本成本（折现率）

**步骤4：计算终值**

使用永续增长模型计算终值：

```
Terminal_FCF = FCF_N × (1 + g)
Terminal_Value = Terminal_FCF / (WACC - g)
```

其中：
- g：永续增长率

**步骤5：计算企业价值和股权价值**

```
企业价值 = Σ(PV(FCF_t)) + PV(Terminal_Value)
股权价值 = 企业价值 - 净债务
```

**步骤6：计算每股内在价值**

```
每股内在价值 = 股权价值 / 总股本
```

#### 6.3.3 关键参数说明

| 参数 | 说明 | 影响 | 默认值 |
|------|------|------|--------|
| **增长率** | 预测期FCF增长率 | 越高，估值越高 | 15% |
| **永续增长率** | 永续阶段的增长率 | 越高，终值越高 | 3% |
| **折现率（WACC）** | 加权平均资本成本 | 越高，估值越低 | 10% |
| **预测期（N）** | 预测自由现金流的年数 | 越长，估值越高 | 5年 |

#### 6.3.4 情景分析与商业模式对应

**三种情景的商业模式映射：**

| 情景 | 永续增长率 | 对应情形 | 商业模式 | 适用行业 | 典型公司 |
|------|-----------|---------|---------|---------|---------|
| **保守** | 1-2% | 情形1：低增长 | 成熟期/衰退期 | 传统制造业、公用事业、银行业 | 浦发银行、京东方A、宝钢股份 |
| **基准** | 3% | 情形2：稳定增长 | 稳定增长期 | 消费品、医药、知名品牌 | 茅台、可口可乐、恒瑞医药 |
| **乐观** | 4-5% | 情形3：高增长 | 高成长期 | 科技公司、新能源、创新药 | 比亚迪、宁德时代、药明康德 |

**情景详细说明：**

**保守情景（情形1：低增长）**

```
商业含义：成熟期/衰退期公司

特征：
- 市场饱和，增长空间有限
- 自由现金流增长放缓
- 永续增长率较低（1-2%）
- 需要高风险折价

适用公司：
  ✓ 传统制造业（钢铁、水泥、纺织）
  ✓ 公用事业（电力、水务、燃气）
  ✓ 传统银行业务
  ✓ 零售连锁（市场饱和）

财务特征：
  T0-TN: FCF 增长率下降 → 接近 GDP 增长
  T+N以后: 永续增长率 1-2%
  增长动力: 市场饱和 + 竞争加剧
```

**基准情景（情形2：稳定增长）**

```
商业含义：稳定增长公司

特征：
- 拥有品牌护城河或技术壁垒
- 自由现金流稳定增长
- 永续增长率适中（3%）
- 估值倍数基准

适用公司：
  ✓ 消费品（知名品牌、重复消费）
  ✓ 医药行业（创新药企、专利壁垒）
  ✓ 科技公司（成熟期的SaaS）
  ✓ 食品饮料（高端品牌、提价能力）

财务特征：
  T0-TN: FCF 稳定增长
  T+N以后: 永续增长率 3%
  增长动力: 品牌效应 + 垄断地位 + 重复消费
```

**乐观情景（情形3：高增长）**

```
商业含义：高成长公司

特征：
- 拥有技术创新或商业模式创新
- 自由现金流持续高增长
- 永续增长率较高（4-5%）
- 估值倍数最高

适用公司：
  ✓ 新兴科技公司（SaaS、AI、云计算）
  ✓ 高端制造业（半导体、新能源）
  ✓ 生物医药（创新药研发）
  ✓ 互联网平台（高成长期）

财务特征：
  T0-TN: FCF 高增长
  T+N以后: 永续增长率 4-5%
  增长动力: 技术创新 + 网络效应 + 规模经济
```

#### 6.3.5 模型适用性说明

**适用场景：**
✓ 现金流稳定或可预测的公司
✓ 拥有持续产生现金流能力的公司
✓ 成熟期或稳定增长期的公司
✓ 资本密集型行业

**不适用场景：**
✗ 现金流波动较大的公司（周期性行业）
✗ 现金流为负或接近零的公司（初创企业）
✗ 高速扩张期的公司（大量资本支出）
✗ 难以预测未来现金流的公司

#### 6.3.6 风险提示

⚠️ **预测假设风险**
- 模型假设未来自由现金流持续增长
- 增长率和永续增长率的假设对估值影响较大
- 实际经营环境可能与预测存在偏差

⚠️ **模型局限**
- 终值占总价值的比重较高（通常占60-80%）
- 对永续增长率敏感（微小变化导致估值大幅波动）
- 未考虑市场情绪和行业竞争变化
- 不适用于现金流为负的公司

---

## 7. 重要说明

1. **数据存储**：只存储基础财务数据（经营活动现金流量、资本性支出、债务、现金），所有计算字段（自由现金流、净债务、企业价值、股权价值）都是实时计算得出

2. **基准年选择**：自动查询最新的现金流量表年报日期作为基准年（T0）

3. **预测数据**：T1-T5的自由现金流是预测值，不存储在数据库中

4. **计算字段**：折现因子、现值、终值等都是计算字段，不需要存储

5. **终值重要性**：终值通常占企业价值的60-80%，对估值结果影响很大

6. **默认预测期**：N默认为5年

---

## 8. 示例计算

假设平安银行的数据：

**输入数据（T0）：**
- 营业利润：500万元
- 所得税费用：125万元
- 减值损失：25万元
- 营运资本增加：80万元（货币资金增加30 + 存货增加40 + 应收增加50 - 应付增加40）
- 资本性支出（购建固定资产）：250万元
- 子公司投资现金：30万元
- 有息债务：500万元
- 现金及现金等价物：300万元
- 总股本：100万股
- WACC：10%
- 预测期增长率：15%
- 永续增长率：3%

**计算过程：**

```
// T0计算（使用新公式）
税后利润 = 500 - 125 = 375万元
折旧和摊销 = 25万元（减值损失，累计折旧已忽略）
营运资本增加 = 80万元
资本支出 = 250 + 30 = 280万元
自由现金流 = 375 + 25 - 80 - 280 = 40万元
净债务 = 500 - 300 = 200万元

// T1-T5预测
T1: FCF = 40 × 1.15 = 46, PV = 46 / 1.1 = 41.8
T2: FCF = 46 × 1.15 = 52.9, PV = 52.9 / 1.21 = 43.7
T3: FCF = 52.9 × 1.15 = 60.8, PV = 60.8 / 1.331 = 45.7
T4: FCF = 60.8 × 1.15 = 69.9, PV = 69.9 / 1.464 = 47.7
T5: FCF = 69.9 × 1.15 = 80.4, PV = 80.4 / 1.611 = 49.9

// 预测期现值总和
Total_PV_FCF = 41.8 + 43.7 + 45.7 + 47.7 + 49.9 = 228.8

// 终值计算
Terminal_FCF = 80.4 × 1.03 = 82.8
Terminal_Value = 82.8 / (0.10 - 0.03) = 1182.9
PV_Terminal_Value = 1182.9 / 1.611 = 734.5

// 企业价值
Enterprise_Value = 228.8 + 734.5 = 963.3

// 股权价值
Equity_Value = 963.3 - 200 = 763.3

// 每股内在价值
Intrinsic_Value_Per_Share = 763.3 / 100 = 7.63元
```

**最终结果：**
- 企业价值：963.3万元
- 股权价值：763.3万元
- 每股内在价值：7.63元

---

## 附录：DCFValuationService代码实现

DCFValuationService位于 `backend/valuation/dcf.py`，实现了完整的DCF估值逻辑。

### 核心方法：

1. `valuate()`: 主估值方法
2. `_get_base_financials()`: 从数据库获取基准财务数据
3. `_calculate_projected_fcf()`: 预测自由现金流
4. `_calculate_terminal_value()`: 计算终值
5. `_calculate_pv_projected_fcf()`: 计算预测期FCF现值
6. `_calculate_pv_terminal_value()`: 计算终值现值

### 科目编码映射（SUBJECT_CODES）：

```python
SUBJECT_CODES = {
    # 利润表科目
    'revenue': ['ISI001'],              # 营业收入
    'operating_income': ['ISF016'],     # 营业利润
    'net_income': ['ISF021'],           # 净利润

    # 资产负债表科目
    'total_assets': ['BSA121'],         # 资产总计
    'total_liabilities': ['BSL112'],    # 负债合计
    'shareholders_equity': ['BSE010'],  # 归属于母公司所有者权益合计
    'shares_outstanding': ['BSE001'],   # 实收资本（或股本）

    # 现金流量表科目
    'operating_cash_flow': ['CFO020'],  # 经营活动产生的现金流量净额
    'capital_expenditure': ['CFIV007'], # 购建固定资产、无形资产和其他长期资产支付的现金

    # 债务科目
    'short_term_debt': ['BSL001', 'BSL002', 'BSL003'],  # 短期借款、向中央银行借款、拆入资金
    'long_term_debt': ['BSL102', 'BSL103'],              # 长期借款、应付债券
    'cash': ['BSA001', 'BSA002', 'BSA003'],              # 货币资金、结算备付金、拆出资金
}
```

---

**文档版本：** v1.0
**最后更新：** 2026-02-07
**作者：** AI Investor Team