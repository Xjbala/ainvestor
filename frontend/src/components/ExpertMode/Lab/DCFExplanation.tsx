import './ModelExplanation.css';

interface DCFExplanationProps {
  onClose: () => void;
}

export function DCFExplanation({ onClose }: DCFExplanationProps) {
  return (
    <div className="model-explanation-overlay">
      <div className="model-explanation-container">
        <div className="model-explanation-header">
          <h2>DCF 现金流折现估值模型</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="model-explanation-content">
          {/* 核心原理 */}
          <section className="explanation-section">
            <h3>📊 核心原理</h3>
            <p>
              DCF（Discounted Cash Flow）模型是基于企业未来现金流的估值方法，核心思想是：
            </p>
            <div className="formula-box">
              <p className="formula">
                企业价值 = 预测期自由现金流现值 + 终值现值
              </p>
              <p className="formula">
                股权价值 = 企业价值 - 净债务
              </p>
              <p className="formula">
                每股内在价值 = 股权价值 / 总股本
              </p>
            </div>
          </section>

          {/* 关键公式 */}
          <section className="explanation-section">
            <h3>🔢 关键公式</h3>
            <div className="formula-list">
              <div className="formula-item">
                <h4>自由现金流（FCF）- 新公式</h4>
                <p className="formula">FCF = 税后利润 + 折旧和摊销 - 营运资本增加 - 资本支出</p>
                <div className="formula-breakdown">
                  <p className="formula-sub">其中：</p>
                  <p className="formula-sub">• 税后利润 = 营业利润 - 所得税费用</p>
                  <p className="formula-sub">• 折旧和摊销 = 减值损失（累计折旧已忽略）</p>
                  <p className="formula-sub">• 营运资本增加 = 货币资金增加 + 存货增加 + 经营性应收增加 - 经营性应付增加</p>
                  <p className="formula-sub">• 资本支出 = 购建固定资产等 + 子公司投资现金</p>
                </div>
                <p className="description">反映企业可以自由分配给股东和债权人的现金</p>
              </div>
              <div className="formula-item">
                <h4>现金流现值</h4>
                <p className="formula">PV(FCF<sub>t</sub>) = FCF<sub>t</sub> / (1 + WACC)<sup>t</sup></p>
                <p className="description">将未来现金流折现到当前时点</p>
              </div>
              <div className="formula-item">
                <h4>终值（永续增长）</h4>
                <p className="formula">TV = FCF<sub>N</sub> × (1 + g) / (WACC - g)</p>
                <p className="description">第N年后永续阶段的现金流价值</p>
              </div>
            </div>
          </section>

          {/* 预测场景 */}
          <section className="explanation-section">
            <h3>📈 预测场景</h3>
            <div className="scenario-grid">
              <div className="scenario-card conservative">
                <h4>保守情景</h4>
                <div className="scenario-assumption">永续增长率: 1-2%</div>
                <p>适用于成熟期/衰退期公司，现金流增长放缓</p>
                <div className="scenario-examples">
                  <strong>典型行业:</strong> 传统制造业、公用事业、银行业
                </div>
              </div>
              <div className="scenario-card base">
                <h4>基准情景</h4>
                <div className="scenario-assumption">永续增长率: 3%</div>
                <p>适用于稳定增长公司，现金流保持平稳</p>
                <div className="scenario-examples">
                  <strong>典型行业:</strong> 消费品、医药、知名品牌
                </div>
              </div>
              <div className="scenario-card optimistic">
                <h4>乐观情景</h4>
                <div className="scenario-assumption">永续增长率: 4-5%</div>
                <p>适用于高成长公司，现金流持续增长</p>
                <div className="scenario-examples">
                  <strong>典型行业:</strong> 科技公司、新能源、创新药
                </div>
              </div>
            </div>
          </section>

          {/* 关键参数 */}
          <section className="explanation-section">
            <h3>⚙️ 关键参数</h3>
            <div className="parameter-table">
              <table>
                <thead>
                  <tr>
                    <th>参数</th>
                    <th>说明</th>
                    <th>影响</th>
                    <th>默认值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>增长率</td>
                    <td>预测期FCF增长率</td>
                    <td>越高，估值越高</td>
                    <td>15%</td>
                  </tr>
                  <tr>
                    <td>永续增长率</td>
                    <td>永续阶段的增长率</td>
                    <td>越高，终值越高</td>
                    <td>3%</td>
                  </tr>
                  <tr>
                    <td>折现率 (WACC)</td>
                    <td>加权平均资本成本</td>
                    <td>越高，估值越低</td>
                    <td>10%</td>
                  </tr>
                  <tr>
                    <td>预测期</td>
                    <td>预测现金流的年数</td>
                    <td>越长，估值越高</td>
                    <td>5年</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* 预测步骤 */}
          <section className="explanation-section">
            <h3>🔄 预测步骤</h3>
            <div className="steps-container">
              <div className="step-item">
                <div className="step-number">1</div>
                <div className="step-content">
                  <h4>获取基准数据</h4>
                  <p>从数据库获取最新的利润表、资产负债表和现金流量表数据</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h4>计算基准FCF</h4>
                  <p>自由现金流 = 税后利润 + 折旧和摊销 - 营运资本增加 - 资本支出</p>
                  <p className="formula-sub">• 营运资本增加 = 货币资金增加 + 存货增加 + 经营性应收增加 - 经营性应付增加</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h4>预测未来FCF</h4>
                  <p>使用增长率预测T1-T5年的自由现金流</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">4</div>
                <div className="step-content">
                  <h4>折现到现值</h4>
                  <p>将预测的FCF按WACC折现到当前时点</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">5</div>
                <div className="step-content">
                  <h4>计算终值</h4>
                  <p>使用永续增长模型计算第N年后的终值</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">6</div>
                <div className="step-content">
                  <h4>计算企业价值</h4>
                  <p>企业价值 = 预测期现值 + 终值现值</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">7</div>
                <div className="step-content">
                  <h4>计算股权价值</h4>
                  <p>股权价值 = 企业价值 - 净债务</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">8</div>
                <div className="step-content">
                  <h4>计算每股价值</h4>
                  <p>每股内在价值 = 股权价值 / 总股本</p>
                </div>
              </div>
            </div>
          </section>

          {/* 适用场景 */}
          <section className="explanation-section">
            <h3>✅ 适用场景</h3>
            <div className="applicability">
              <div className="applicability-item applicable">
                <h4>✓ 适用于</h4>
                <ul>
                  <li>现金流稳定或可预测的公司</li>
                  <li>拥有持续产生现金流能力的公司</li>
                  <li>成熟期或稳定增长期的公司</li>
                  <li>资本密集型行业</li>
                </ul>
              </div>
              <div className="applicability-item not-applicable">
                <h4>✗ 不适用于</h4>
                <ul>
                  <li>现金流波动较大的公司（周期性行业）</li>
                  <li>现金流为负或接近零的公司（初创企业）</li>
                  <li>高速扩张期的公司（大量资本支出）</li>
                  <li>难以预测未来现金流的公司</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 风险提示 */}
          <section className="explanation-section warning">
            <h3>⚠️ 风险提示</h3>
            <ul className="warning-list">
              <li><strong>预测假设风险：</strong>模型假设未来自由现金流持续增长，增长率和永续增长率的假设对估值影响较大</li>
              <li><strong>终值敏感性：</strong>终值通常占企业价值的60-80%，对估值结果影响很大</li>
              <li><strong>永续增长率敏感性：</strong>永续增长率的微小变化会导致估值大幅波动</li>
              <li><strong>模型局限：</strong>未考虑市场情绪和行业竞争变化，不适用于现金流为负的公司</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}