import './ModelExplanation.css';

interface RIMExplanationProps {
  onClose: () => void;
}

export function RIMExplanation({ onClose }: RIMExplanationProps) {
  return (
    <div className="model-explanation-overlay">
      <div className="model-explanation-container">
        <div className="model-explanation-header">
          <h2>RIM 剩余收益估值模型</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="model-explanation-content">
          {/* 核心原理 */}
          <section className="explanation-section">
            <h3>📊 核心原理</h3>
            <p>
              RIM（Residual Income Model）模型基于净资产的会计价值，核心思想是：
            </p>
            <div className="formula-box">
              <p className="formula">
                每股价值 = 初始每股净资产 + 未来剩余收益的现值
              </p>
            </div>
            <p className="description">
              剩余收益是指企业创造的收益超过其资本成本的部分，反映了企业为股东创造的真实价值。
            </p>
          </section>

          {/* 关键公式 */}
          <section className="explanation-section">
            <h3>🔢 关键公式</h3>
            <div className="formula-list">
              <div className="formula-item">
                <h4>剩余收益（RE）</h4>
                <p className="formula">RE<sub>t</sub> = EPS<sub>t</sub> - r × BPS<sub>t-1</sub></p>
                <p className="description">
                  RE<sub>t</sub>: 第t年的剩余收益<br/>
                  EPS<sub>t</sub>: 第t年的每股收益<br/>
                  r: 要求回报率（股权成本）<br/>
                  BPS<sub>t-1</sub>: 第t-1年的每股净资产
                </p>
              </div>
              <div className="formula-item">
                <h4>每股价值</h4>
                <p className="formula">V₀ = BPS₀ + Σ(PV(RE<sub>t</sub>))</p>
                <p className="description">
                  V₀: 每股内在价值<br/>
                  BPS₀: 初始每股净资产<br/>
                  PV(RE<sub>t</sub>): 剩余收益的现值
                </p>
              </div>
              <div className="formula-item">
                <h4>剩余收益现值</h4>
                <p className="formula">PV(RE<sub>t</sub>) = RE<sub>t</sub> / (1 + r)<sup>t</sup></p>
                <p className="description">将剩余收益折现到当前时点</p>
              </div>
            </div>
          </section>

          {/* 预测场景 */}
          <section className="explanation-section">
            <h3>📈 预测场景</h3>
            <div className="scenario-grid">
              <div className="scenario-card conservative">
                <h4>保守情景</h4>
                <div className="scenario-assumption">RE趋势: 递减 → 接近0</div>
                <p>假设第N年后剩余收益归零，ROE下降到股权成本</p>
                <div className="scenario-examples">
                  <strong>典型公司:</strong> 浦发银行、京东方A、宝钢股份
                </div>
              </div>
              <div className="scenario-card base">
                <h4>基准情景</h4>
                <div className="scenario-assumption">RE趋势: 稳定 → 保持常数</div>
                <p>假设第N年后剩余收益保持恒定，维持超额收益能力</p>
                <div className="scenario-examples">
                  <strong>典型公司:</strong> 茅台、可口可乐、恒瑞医药
                </div>
              </div>
              <div className="scenario-card optimistic">
                <h4>乐观情景</h4>
                <div className="scenario-assumption">RE趋势: 递增 → 持续增长</div>
                <p>假设第N年后剩余收益继续增长，持续创造超额价值</p>
                <div className="scenario-examples">
                  <strong>典型公司:</strong> 比亚迪、宁德时代、药明康德
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
                    <td>股权成本</td>
                    <td>投资者要求的最低收益率</td>
                    <td>越高，估值越低</td>
                    <td>9%</td>
                  </tr>
                  <tr>
                    <td>增长率</td>
                    <td>预测期EPS增长率</td>
                    <td>越高，估值越高</td>
                    <td>15%</td>
                  </tr>
                  <tr>
                    <td>股利支付率</td>
                    <td>净利润中分红的比例</td>
                    <td>越高，BPS增长越慢</td>
                    <td>30%</td>
                  </tr>
                  <tr>
                    <td>预测期</td>
                    <td>预测剩余收益的年数</td>
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
                  <p>从数据库获取最新的净利润、股东权益、股本数据</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h4>计算每股数据</h4>
                  <p>EPS = 净利润 / 股本<br/>BPS = 股东权益 / 股本</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h4>预测未来EPS</h4>
                  <p>使用增长率预测T1-T5年的每股收益</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">4</div>
                <div className="step-content">
                  <h4>计算BPS和DPS</h4>
                  <p>递推计算每股净资产和每股股利</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">5</div>
                <div className="step-content">
                  <h4>计算ROE和RE</h4>
                  <p>ROE = EPS / BPS<sub>t-1</sub><br/>RE = EPS - r × BPS<sub>t-1</sub></p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">6</div>
                <div className="step-content">
                  <h4>分析RE趋势</h4>
                  <p>分析T1-T5年的剩余收益趋势（递减/稳定/递增）</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">7</div>
                <div className="step-content">
                  <h4>计算情景估值</h4>
                  <p>根据RE趋势计算保守/基准/乐观三种情景的估值</p>
                </div>
              </div>
              <div className="step-item">
                <div className="step-number">8</div>
                <div className="step-content">
                  <h4>计算每股价值</h4>
                  <p>每股价值 = BPS₀ + 剩余收益现值 + 终值现值</p>
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
                  <li>ROE持续高于要求回报率的公司</li>
                  <li>账面价值较为稳定的公司</li>
                  <li>高增长但分红率较低的公司</li>
                  <li>估值需要基于会计数据的公司</li>
                </ul>
              </div>
              <div className="applicability-item not-applicable">
                <h4>✗ 不适用于</h4>
                <ul>
                  <li>周期性较强的公司（波动大）</li>
                  <li>ROE低于要求回报率的公司（剩余收益为负）</li>
                  <li>账面价值失真的公司（如金融企业特殊处理）</li>
                  <li>快速扩张期的初创企业</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 风险提示 */}
          <section className="explanation-section warning">
            <h3>⚠️ 风险提示</h3>
            <ul className="warning-list">
              <li><strong>预测假设风险：</strong>模型假设未来ROE持续高于要求回报率，增长率和股利支付率的假设对估值影响较大</li>
              <li><strong>模型局限：</strong>N年后RE的假设可能过于乐观或悲观，未考虑市场情绪和行业竞争变化</li>
              <li><strong>会计政策影响：</strong>会计政策变更可能影响账面价值，从而影响估值结果</li>
              <li><strong>终值敏感性：</strong>终值假设对估值结果有较大影响，需要谨慎选择</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}