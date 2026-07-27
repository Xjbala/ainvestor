# -*- coding: utf-8 -*-
"""
新浪财经爬虫服务

移植自 leofun 项目的新浪财经数据爬取逻辑。
提供股票列表、财务报表等数据采集能力。
"""

import asyncio
import logging
import re
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base import CrawlerService, parse_decimal
from ..persistence.db import async_session_factory
from ..persistence.financial_models import (
    Company,
    AccountSubject,
    FinancialSubjectMapping,
    FinancialData,
    ReportType,
    ReportPeriod,
    Exchange,
    Industry,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 新浪财经 JSON API 地址
SINA_JSON_API_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"

# 新浪科目名 -> 标准科目编码（现有编码体系下的别名表）
# 优先于模糊匹配，避免“利息收入/其他综合收益”等被错误归并。
SINA_SUBJECT_ALIASES: Dict[str, Dict[str, str]] = {
    "BS": {
        "货币资金": "BSA001",
        "结算备付金": "BSA002",
        "拆出资金": "BSA003",
        "交易性金融资产": "BSA004",
        "衍生金融资产": "BSA005",
        "应收票据": "BSA006",
        "应收账款": "BSA007",
        "应收票据及应收账款": "BSA007",
        "应收款项融资": "BSA008",
        "预付款项": "BSA009",
        "应收保费": "BSA010",
        "应收分保账款": "BSA011",
        "应收分保合同准备金": "BSA012",
        "其他应收款": "BSA013",
        "其他应收款(合计)": "BSA013",
        "其他应收款合计": "BSA013",
        "买入返售金融资产": "BSA014",
        "存货": "BSA015",
        "合同资产": "BSA016",
        "持有待售资产": "BSA017",
        "划分为持有待售的资产": "BSA017",
        "一年内到期的非流动资产": "BSA018",
        "其他流动资产": "BSA019",
        "流动资产合计": "BSA020",
        "应收股利": "BSA021",
        "应收利息": "BSA022",
        "发放贷款和垫款": "BSA101",
        "发放贷款及垫款": "BSA101",
        "债权投资": "BSA102",
        "其他债权投资": "BSA103",
        "可供出售金融资产": "BSA106",
        "以公允价值计量且其变动计入其他综合收益的金融资产": "BSA106",
        "以摊余成本计量的金融资产": "BSA102",
        "长期应收款": "BSA104",
        "长期股权投资": "BSA105",
        "其他权益工具投资": "BSA106",
        "其他非流动金融资产": "BSA107",
        "投资性房地产": "BSA108",
        "固定资产": "BSA109",
        "固定资产净额": "BSA109",
        "固定资产净值": "BSA109",
        "固定资产及清理合计": "BSA109",
        "固定资产原值": "BSA109",
        "在建工程": "BSA110",
        "在建工程合计": "BSA110",
        "工程物资": "BSA110",
        "生产性生物资产": "BSA111",
        "油气资产": "BSA112",
        "使用权资产": "BSA113",
        "无形资产": "BSA114",
        "开发支出": "BSA115",
        "商誉": "BSA116",
        "长期待摊费用": "BSA117",
        "递延所得税资产": "BSA118",
        "其他非流动资产": "BSA119",
        "非流动资产合计": "BSA120",
        "资产总计": "BSA121",
        "短期借款": "BSL001",
        "向中央银行借款": "BSL002",
        "拆入资金": "BSL003",
        "交易性金融负债": "BSL004",
        "衍生金融负债": "BSL005",
        "应付票据": "BSL006",
        "应付账款": "BSL007",
        "应付票据及应付账款": "BSL007",
        "预收款项": "BSL008",
        "合同负债": "BSL009",
        "卖出回购金融资产款": "BSL010",
        "吸收存款及同业存放": "BSL011",
        "代理买卖证券款": "BSL012",
        "代理承销证券款": "BSL013",
        "应付职工薪酬": "BSL014",
        "应交税费": "BSL015",
        "其他应付款": "BSL016",
        "其他应付款合计": "BSL016",
        "应付手续费及佣金": "BSL017",
        "应付分保账款": "BSL018",
        "持有待售负债": "BSL019",
        "划分为持有待售的负债": "BSL019",
        "一年内到期的非流动负债": "BSL020",
        "其他流动负债": "BSL021",
        "流动负债合计": "BSL022",
        "应付股利": "BSL023",
        "应付利息": "BSL024",
        "保险合同准备金": "BSL101",
        "长期借款": "BSL102",
        "应付债券": "BSL103",
        "租赁负债": "BSL104",
        "长期应付款": "BSL105",
        "长期应付款合计": "BSL105",
        "专项应付款": "BSL105",
        "长期应付职工薪酬": "BSL106",
        "预计负债": "BSL107",
        "预计非流动负债": "BSL107",
        "预计流动负债": "BSL107",
        "递延收益": "BSL108",
        "长期递延收益": "BSL108",
        "一年内的递延收益": "BSL108",
        "递延所得税负债": "BSL109",
        "其他非流动负债": "BSL110",
        "非流动负债合计": "BSL111",
        "负债合计": "BSL112",
        "实收资本（或股本）": "BSE001",
        "实收资本(或股本)": "BSE001",
        "其他权益工具": "BSE002",
        "永续债": "BSE002",
        "优先股": "BSE002",
        "资本公积": "BSE003",
        "库存股": "BSE004",
        "减:库存股": "BSE004",
        "减：库存股": "BSE004",
        "其他综合收益": "BSE005",
        "专项储备": "BSE006",
        "盈余公积": "BSE007",
        "一般风险准备": "BSE008",
        "未分配利润": "BSE009",
        "归属于母公司所有者权益合计": "BSE010",
        "归属于母公司股东权益合计": "BSE010",
        "归属于母公司股东的权益": "BSE010",
        "少数股东权益": "BSE011",
        "所有者权益（或股东权益）合计": "BSE012",
        "所有者权益(或股东权益)合计": "BSE012",
        "负债和所有者权益（或股东权益）总计": "BSE013",
        "负债和所有者权益(或股东权益)总计": "BSE013",
        "负债及股东权益总计": "BSE013",
    },
    "IS": {
        "营业收入": "ISI001",
        "利息收入": "ISI002",
        "已赚保费": "ISI003",
        "手续费及佣金收入": "ISI004",
        "营业总收入": "ISI005",
        "营业成本": "ISC001",
        "利息支出": "ISC002",
        "手续费及佣金支出": "ISC003",
        "退保金": "ISC004",
        "赔付支出净额": "ISC005",
        "提取保险合同准备金净额": "ISC006",
        "保单红利支出": "ISC007",
        "分保费用": "ISC008",
        "营业税金及附加": "ISC009",
        "税金及附加": "ISC009",
        "营业总成本": "ISC010",
        "销售费用": "ISF001",
        "管理费用": "ISF002",
        "业务及管理费用": "ISF002",
        "研发费用": "ISF003",
        "财务费用": "ISF004",
        "其中：利息费用": "ISF005",
        "利息费用": "ISF005",
        "财务费用-利息费用": "ISF005",
        "财务费用-利息收入": "ISF006",
        # 财务费用明细里的利息收入（由 _disambiguate_subject_name 改写）
        "其他收益": "ISF007",
        "加：其他收益": "ISF007",
        "投资收益": "ISF008",
        "投资收益（损失以“-”号填列）": "ISF008",
        "对联营企业和合营企业的投资收益": "ISF009",
        "其中：对联营企业和合营企业的投资收益": "ISF009",
        "以摊余成本计量的金融资产终止确认产生的收益": "ISF010",
        "以摊余成本计量的金融资产终止确认收益（损失）": "ISF010",
        "汇兑收益": "ISF011",
        "汇兑收益（损失以“-”号填列）": "ISF011",
        "净敞口套期收益": "ISF012",
        "公允价值变动收益": "ISF013",
        "公允价值变动收益（损失以“-”号填列）": "ISF013",
        "信用减值损失": "ISF014",
        "信用减值损失（转回以“-”号填列）": "ISF014",
        "资产处置收益": "ISF015",
        "资产处置收益（损失以“-”号填列）": "ISF015",
        "营业利润": "ISF016",
        "营业利润（亏损以“-”号填列）": "ISF016",
        "营业外收入": "ISF017",
        "加：营业外收入": "ISF017",
        "营业外支出": "ISF018",
        "减：营业外支出": "ISF018",
        "利润总额": "ISF019",
        "利润总额（亏损总额以“-”号填列）": "ISF019",
        "所得税费用": "ISF020",
        "减：所得税费用": "ISF020",
        "净利润": "ISF021",
        "净利润（净亏损以“-”号填列）": "ISF021",
        "持续经营净利润": "ISF023",
        "1.持续经营净利润（净亏损以“-”号填列）": "ISF023",
        "终止经营净利润": "ISF024",
        "2.终止经营净利润（净亏损以“-”号填列）": "ISF024",
        "归属于母公司所有者的净利润": "ISF026",
        "1.归属于母公司所有者的净利润（净亏损以-号填列）": "ISF026",
        "少数股东损益": "ISF027",
        "2.少数股东损益": "ISF027",
        "资产减值损失": "ISF028",
        "资产减值损失（转回以“-”号填列）": "ISF028",
        "其他综合收益": "ISO001",
        "归属于母公司所有者的其他综合收益": "ISO002",
        "归属母公司所有者的其他综合收益": "ISO002",
        "归属于少数股东的其他综合收益": "ISO003",
        "少数股东其他综合收益": "ISO003",
        "综合收益总额": "ISO004",
        "归属于母公司所有者的综合收益总额": "ISO005",
        "归属于少数股东的综合收益总额": "ISO006",
        "基本每股收益": "ISE001",
        "（一）基本每股收益": "ISE001",
        "稀释每股收益": "ISE002",
        "（二）稀释每股收益": "ISE002",
    },
    "CF": {
        "销售商品、提供劳务收到的现金": "CFO001",
        "客户存款和同业存放款项净增加额": "CFO002",
        "向中央银行借款净增加额": "CFO003",
        "向其他金融机构拆入资金净增加额": "CFO004",
        "收取利息、手续费及佣金的现金": "CFO005",
        "拆入资金净增加额": "CFO006",
        "回购业务资金净增加额": "CFO007",
        "代理买卖证券收到的现金净额": "CFO008",
        "收到的税费返还": "CFO009",
        "收到其他与经营活动有关的现金": "CFO010",
        "收到的其他与经营活动有关的现金": "CFO010",
        "经营活动现金流入小计": "CFO011",
        "购买商品、接受劳务支付的现金": "CFO012",
        "客户贷款及垫款净增加额": "CFO013",
        "存放中央银行和同业款项净增加额": "CFO014",
        "支付利息、手续费及佣金的现金": "CFO015",
        "支付给职工以及为职工支付的现金": "CFO016",
        "支付的各项税费": "CFO017",
        "支付其他与经营活动有关的现金": "CFO018",
        "支付的其他与经营活动有关的现金": "CFO018",
        "经营活动现金流出小计": "CFO019",
        "经营活动产生的现金流量净额": "CFO020",
        "收回投资收到的现金": "CFIV001",
        "收回投资所收到的现金": "CFIV001",
        "取得投资收益收到的现金": "CFIV002",
        "处置固定资产、无形资产和其他长期资产收回的现金净额": "CFIV003",
        "处置固定资产、无形资产和其他长期资产所收回的现金净额": "CFIV003",
        "处置子公司及其他营业单位收到的现金净额": "CFIV004",
        "收到其他与投资活动有关的现金": "CFIV005",
        "收到的其他与投资活动有关的现金": "CFIV005",
        "投资活动现金流入小计": "CFIV006",
        "购建固定资产、无形资产和其他长期资产支付的现金": "CFIV007",
        "购建固定资产、无形资产和其他长期资产所支付的现金": "CFIV007",
        "投资支付的现金": "CFIV008",
        "投资所支付的现金": "CFIV008",
        "取得子公司及其他营业单位支付的现金净额": "CFIV009",
        "支付其他与投资活动有关的现金": "CFIV010",
        "支付的其他与投资活动有关的现金": "CFIV010",
        "投资活动现金流出小计": "CFIV011",
        "投资活动产生的现金流量净额": "CFIV012",
        "吸收投资收到的现金": "CFFN001",
        "其中：子公司吸收少数股东投资收到的现金": "CFFN002",
        "子公司吸收少数股东投资收到的现金": "CFFN002",
        "取得借款收到的现金": "CFFN003",
        "发行债券收到的现金": "CFFN003",
        "收到其他与筹资活动有关的现金": "CFFN004",
        "筹资活动现金流入小计": "CFFN005",
        "偿还债务支付的现金": "CFFN006",
        "分配股利、利润或偿付利息支付的现金": "CFFN007",
        "分配股利、利润或偿付利息所支付的现金": "CFFN007",
        "其中：子公司支付给少数股东的股利、利润": "CFFN008",
        "子公司支付给少数股东的股利、利润": "CFFN008",
        "支付其他与筹资活动有关的现金": "CFFN009",
        "筹资活动现金流出小计": "CFFN010",
        "筹资活动产生的现金流量净额": "CFFN011",
        "现金及现金等价物净增加额": "CFT001",
        "加：期初现金及现金等价物余额": "CFT002",
        "期初现金及现金等价物余额": "CFT002",
        "现金的期初余额": "CFT002",
        "现金等价物的期初余额": "CFT002",
        "期末现金及现金等价物余额": "CFT003",
        "现金的期末余额": "CFT003",
        "现金等价物的期末余额": "CFT003",
        "汇率变动对现金及现金等价物的影响": "CFX001",
    },
}

# 分区标题 / 纯结构行，不落库
_SECTION_TITLES = {
    "流动资产",
    "非流动资产",
    "流动负债",
    "非流动负债",
    "所有者权益",
    "经营活动产生的现金流量",
    "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
}


def _normalize_subject_name(name: str) -> str:
    """标准化科目名称，便于跨源匹配。"""
    if not name:
        return ""
    text = str(name).strip()
    table = str.maketrans({
        "（": "(",
        "）": ")",
        "：": ":",
        "，": ",",
        "；": ";",
        "－": "-",
        "—": "-",
        "–": "-",
        "　": " ",
        "＋": "+",
        "＋": "+",
    })
    text = text.translate(table)
    text = re.sub(r"\s+", "", text)
    # 去掉常见填列说明
    text = re.sub(r"[（(][^）)]*[损失亏损转回填列][^）)]*[）)]", "", text)
    text = text.replace("加:", "").replace("减:", "").replace("其中:", "")
    text = text.replace("加：", "").replace("减：", "").replace("其中：", "")
    # 去掉序号前缀：1. / （一） / 1、
    text = re.sub(r"^[0-9]+[\.、]", "", text)
    text = re.sub(r"^[（(][一二三四五六七八九十0-9]+[）)]", "", text)
    return text


class SinaCrawlerService(CrawlerService):
    """
    新浪财经爬虫服务

    数据来源：
    - 股票列表：新浪财经行情中心
    - 财务报表：新浪财经财务数据
    """

    # 新浪财经 API 地址
    STOCK_LIST_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    REPORT_URL = "https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/{stock_code}/displaytype/4.phtml"

    # 财务数据 API (JSON)
    # source: fzb=资产负债表, lrb=利润表, llb=现金流量表
    # page/num 支持分页；num=50 可覆盖较完整历史
    REPORT_JSON_URL = (
        SINA_JSON_API_URL
        + "?paperCode={paper_code}&source={source}&type=0&page={page}&num={num}"
    )
    REPORT_PAGE_SIZE = 50
    REPORT_MAX_PAGES = 5

    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }

    def __init__(self, session, **kwargs):
        super().__init__(session, data_source_code="sina", **kwargs)
        # 科目匹配缓存：避免每个科目都打库
        self._subject_cache_loaded = False
        self._subjects_by_rt: Dict[str, List[AccountSubject]] = {}
        self._subjects_by_code: Dict[str, AccountSubject] = {}
        self._name_index: Dict[str, Dict[str, AccountSubject]] = {}
        self._norm_index: Dict[str, Dict[str, AccountSubject]] = {}
        self._mapping_by_name: Dict[str, AccountSubject] = {}
        self._unmatched_names: Dict[str, set] = {"BS": set(), "IS": set(), "CF": set()}

    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """
        爬取 A 股公司列表

        Returns:
            公司信息列表，每个公司包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - exchange: 交易所 (sh/sz)
            - current_price: 当前价格
            - change_percent: 涨跌幅
        """
        companies = []

        # 爬取沪市股票
        sh_companies = await self._crawl_stock_list("sh_a")
        companies.extend(sh_companies)

        # 爬取深市股票
        sz_companies = await self._crawl_stock_list("sz_a")
        companies.extend(sz_companies)

        logger.info(f"Crawled {len(companies)} companies from Sina Finance")
        return companies

    async def save_companies(self, companies: List[Dict[str, Any]]):
        """保存公司列表到数据库"""
        if not companies:
            return
        
        async with async_session_factory() as session:
            # 获取或创建交易所
            exchanges = {}
            for ex_code in ["sh", "sz"]:
                stmt = select(Exchange).where(Exchange.code == ex_code)
                result = await session.execute(stmt)
                ex = result.scalar_one_or_none()
                if not ex:
                    ex = Exchange(code=ex_code, name="上海证券交易所" if ex_code == "sh" else "深圳证券交易所", country="中国")
                    session.add(ex)
                    await session.flush()
                exchanges[ex_code] = ex.id

            for item in companies:
                stock_code = item["stock_code"]
                stmt = select(Company).where(Company.stock_code == stock_code)
                result = await session.execute(stmt)
                company = result.scalars().first()
                
                if company:
                    company.stock_name = item.get("stock_name", company.stock_name)
                    company.pe_ratio = item.get("pe_ratio", company.pe_ratio)
                    company.pb_ratio = item.get("pb_ratio", company.pb_ratio)
                    company.market_cap = item.get("market_cap", company.market_cap)
                else:
                    company = Company(
                        stock_code=stock_code,
                        stock_name=item.get("stock_name"),
                        exchange_id=exchanges.get(item.get("exchange", "sh")),
                        company_name=item.get("stock_name"), # 简化处理
                        status="active",
                        pe_ratio=item.get("pe_ratio"),
                        pb_ratio=item.get("pb_ratio"),
                        market_cap=item.get("market_cap")
                    )
                    session.add(company)
            
            await session.commit()
            logger.info(f"Saved {len(companies)} companies to DB")

    async def _crawl_stock_list(
        self,
        node: str,
        page: int = 1,
        num: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        爬取单个市场的股票列表

        Args:
            node: 市场节点 (sh_a/sz_a)
            page: 页码
            num: 每页数量

        Returns:
            股票列表
        """
        params = {
            "node": node,
            "page": page,
            "num": num,
            "_s_r_a": "auto",
        }

        data = await self.fetch_json(self.STOCK_LIST_URL, headers=self.HEADERS, params=params)

        if not data:
            logger.warning(f"Failed to fetch stock list for {node}")
            return []

        companies = []
        for item in data:
            try:
                # 解析股票代码
                symbol = item.get("symbol", "")
                exchange = "sh" if symbol.startswith("sh") else "sz"
                stock_code = symbol[2:] if len(symbol) > 2 else symbol

                companies.append({
                    "stock_code": stock_code,
                    "stock_name": item.get("name", ""),
                    "exchange": exchange,
                    "current_price": parse_decimal(item.get("trade")),
                    "change_percent": parse_decimal(item.get("changepercent")),
                    "volume": parse_decimal(item.get("volume")),
                    "turnover": parse_decimal(item.get("amount")),
                    "pe_ratio": parse_decimal(item.get("pe")),
                    "pb_ratio": parse_decimal(item.get("pb")),
                    "market_cap": parse_decimal(item.get("mktcap")),
                })
            except Exception as e:
                logger.error(f"Failed to parse stock item: {e}")
                continue

        return companies

    async def crawl_financial_report(
        self,
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        爬取财务报表数据 (JSON API)

        Args:
            stock_code: 股票代码
            report_type: 报表类型 (BS/IS/CF)
            year: 目标年份 (如果指定，仅返回该年份数据)

        Returns:
            财务数据列表
        """
        source_map = {
            "BS": "fzb",
            "IS": "lrb",
            "CF": "llb",
        }

        source = source_map.get(report_type)
        if not source:
            logger.error(f"Unknown report type: {report_type}")
            return []

        # 确定交易所前缀
        exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
        paper_code = f"{exchange_prefix}{stock_code}"

        financial_data_list: List[Dict[str, Any]] = []
        seen_periods: set = set()
        report_count = None

        for page in range(1, self.REPORT_MAX_PAGES + 1):
            url = self.REPORT_JSON_URL.format(
                paper_code=paper_code,
                source=source,
                page=page,
                num=self.REPORT_PAGE_SIZE,
            )
            logger.info(
                f"[Sina] 拉取财报 {stock_code} type={report_type} year={year or 'all'} "
                f"paper={paper_code} page={page} url={url}"
            )
            data = await self.fetch_json(url, headers=self.HEADERS)

            if not data or "result" not in data:
                logger.warning(
                    f"[Sina] 拉取失败 {stock_code} {report_type} page={page}: 无有效响应"
                )
                break

            result = data["result"]
            if result.get("status", {}).get("code") != 0:
                logger.error(
                    f"[Sina] API 错误 {stock_code} {report_type} page={page}: "
                    f"{result.get('status', {}).get('msg')}"
                )
                break

            data_section = result.get("data", {}) or {}
            if report_count is None:
                report_count = data_section.get("report_count")

            page_items, page_periods = self._parse_report_section(
                data_section=data_section,
                stock_code=stock_code,
                report_type=report_type,
                year=year,
            )
            if not page_periods:
                # 无更多期数
                break

            new_periods = [p for p in page_periods if p not in seen_periods]
            if not new_periods and page > 1:
                break

            for p in page_periods:
                seen_periods.add(p)
            financial_data_list.extend(page_items)

            logger.info(
                f"[Sina] {stock_code} {report_type} page={page} "
                f"本期={len(page_periods)} 累计期数={len(seen_periods)} "
                f"累计科目行={len(financial_data_list)} report_count={report_count}"
            )

            # 已拉全，或本页不足一页，停止
            if report_count and len(seen_periods) >= int(report_count):
                break
            if len(page_periods) < self.REPORT_PAGE_SIZE:
                break

        if financial_data_list:
            periods = sorted(seen_periods)
            logger.info(
                f"[Sina] {stock_code} {report_type} 解析完成: "
                f"{len(financial_data_list)} 条科目, 报告期数={len(periods)}, "
                f"范围={periods[0]}~{periods[-1]}"
            )
        else:
            logger.warning(f"[Sina] {stock_code} {report_type} 解析结果为空")
        return financial_data_list

    def _parse_report_section(
        self,
        data_section: Dict[str, Any],
        stock_code: str,
        report_type: str,
        year: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """解析单页 API 响应中的报表数据。"""
        financial_data_list: List[Dict[str, Any]] = []
        periods: List[str] = []

        # 处理 report_list 结构 (2022 API)
        if "report_list" in data_section:
            report_list = data_section.get("report_list") or {}
            period_keys = list(report_list.keys())
            for date_key, date_payload in report_list.items():
                if year and not str(date_key).startswith(str(year)):
                    continue
                if len(str(date_key)) != 8:
                    continue

                report_date_str = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
                periods.append(report_date_str)

                items = (date_payload or {}).get("data", []) or []
                last_major = ""
                for item in items:
                    subject_name = (item.get("item_title") or "").strip()
                    if not subject_name or subject_name in _SECTION_TITLES:
                        continue
                    item_val = item.get("item_value")
                    display_type = item.get("item_display_type")
                    # 记录最近主科目，用于区分同名明细（如财务费用下的利息收入）
                    try:
                        dt_int = int(display_type) if display_type is not None else 99
                    except (TypeError, ValueError):
                        dt_int = 99
                    if dt_int in (1, 2, 6) and subject_name not in (
                        "利息收入",
                        "利息费用",
                        "利息支出",
                    ):
                        last_major = subject_name

                    resolved_name = self._disambiguate_subject_name(
                        subject_name, report_type, last_major, dt_int
                    )
                    parsed_val = self._parse_financial_value(
                        None if item_val is None else str(item_val)
                    )
                    if parsed_val is not None:
                        financial_data_list.append({
                            "stock_code": stock_code,
                            "subject_name": resolved_name,
                            "report_date": report_date_str,
                            "report_type": report_type,
                            "value": parsed_val,
                            "display_type": display_type,
                            "raw_subject_name": subject_name,
                        })
            return financial_data_list, periods

        # 降级方案：旧版 report_data 结构
        report_dates: List[str] = []
        if "report_date" in data_section:
            for date_info in data_section.get("report_date") or []:
                date_val = date_info.get("date_value", "")
                if len(date_val) == 8:
                    formatted_date = f"{date_val[:4]}-{date_val[4:6]}-{date_val[6:8]}"
                    report_dates.append(formatted_date)

        if "report_data" in data_section:
            for report in data_section.get("report_data") or []:
                subject_name = (report.get("subject_name") or "").strip()
                if not subject_name or subject_name in _SECTION_TITLES:
                    continue
                values = report.get("values", []) or []
                for idx, val in enumerate(values):
                    if idx >= len(report_dates):
                        continue
                    report_date_str = report_dates[idx]
                    if year and not report_date_str.startswith(str(year)):
                        continue
                    parsed_val = self._parse_financial_value(str(val))
                    if parsed_val is not None:
                        financial_data_list.append({
                            "stock_code": stock_code,
                            "subject_name": subject_name,
                            "report_date": report_date_str,
                            "report_type": report_type,
                            "value": parsed_val,
                        })
            periods = list(report_dates)
            if year:
                periods = [p for p in periods if p.startswith(str(year))]

        return financial_data_list, periods

    def _parse_financial_value(self, value_text: str) -> Optional[Decimal]:
        """解析财务数值"""
        if not value_text or value_text in ["--", "---", "N/A", "n/a", "", " ", "null", "None"]:
            return None
        try:
            # 清理数值文本
            cleaned = value_text.replace(",", "").strip()
            return Decimal(cleaned)
        except Exception:
            return None

    @staticmethod
    def _disambiguate_subject_name(
        subject_name: str,
        report_type: str,
        last_major: str,
        display_type: int,
    ) -> str:
        """
        根据上下文消解同名科目。

        典型场景：利润表中「利息收入」既可能是金融企业营业收入明细(ISI002)，
        也可能是财务费用下的利息收入明细(ISF006)。
        """
        if report_type != "IS":
            return subject_name

        if subject_name == "利息收入":
            # 仅当处于财务费用段落时，记为财务费用明细
            if "财务费用" in (last_major or ""):
                return "财务费用-利息收入"
            return "利息收入"

        if subject_name in ("利息费用", "其中：利息费用"):
            return "利息费用"

        return subject_name

    async def save_to_db(self, financial_data_list: List[Dict[str, Any]]):
        """保存财务数据到数据库（批量 upsert，避免逐行查询）。"""
        if not financial_data_list:
            return

        # 优先复用爬虫自身 session，避免长任务后新建连接触发连接池兼容问题
        owns_session = False
        session = getattr(self, "session", None)
        if session is None:
            session = async_session_factory()
            owns_session = True

        try:
            await self._persist_financial_data(session, financial_data_list)
        finally:
            if owns_session:
                await session.close()

    async def _persist_financial_data(
        self,
        session,
        financial_data_list: List[Dict[str, Any]],
    ) -> None:
        """在指定 session 上执行财务数据落库。"""
        stock_code = financial_data_list[0]["stock_code"]

        stmt = select(Company).where(Company.stock_code == stock_code)
        result = await session.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            logger.warning(f"Company {stock_code} not found in DB")
            return

        await self._ensure_subject_cache(session)

        # 去重：(report_date, subject_id) -> item
        processed_items: Dict[Tuple[date, int], Dict[str, Any]] = {}
        matched_count = 0
        unmatched_count = 0
        report_dates_seen = set()

        for data in financial_data_list:
            subject_name = data["subject_name"]
            report_type = data["report_type"]
            report_date = date.fromisoformat(data["report_date"])
            display_type = data.get("display_type")

            subject, match_rank = self._match_subject_cached(subject_name, report_type)
            if not subject:
                unmatched_count += 1
                continue

            matched_count += 1
            report_dates_seen.add(report_date)
            key = (report_date, subject.id)
            quality = self._match_quality(subject_name, subject, display_type, match_rank)
            if key in processed_items:
                prev = processed_items[key]
                if quality < prev["quality"]:
                    processed_items[key] = {
                        "data": data,
                        "subject": subject,
                        "match_rank": match_rank,
                        "quality": quality,
                    }
                continue

            processed_items[key] = {
                "data": data,
                "subject": subject,
                "match_rank": match_rank,
                "quality": quality,
            }

        if not processed_items:
            logger.warning(
                f"No matched subjects to save for {stock_code} "
                f"(unmatched_rows={unmatched_count})"
            )
            return

        # 预加载已有记录，避免 N+1
        existing_map: Dict[Tuple[date, int, str], FinancialData] = {}
        date_list = sorted(report_dates_seen)
        batch_size = 40
        for i in range(0, len(date_list), batch_size):
            batch_dates = date_list[i: i + batch_size]
            stmt = select(FinancialData).where(
                FinancialData.company_code == stock_code,
                FinancialData.report_date.in_(batch_dates),
            )
            res = await session.execute(stmt)
            for row in res.scalars().all():
                rt_val = (
                    row.report_type.value
                    if hasattr(row.report_type, "value")
                    else str(row.report_type)
                )
                existing_map[(row.report_date, row.subject_id, rt_val)] = row

        updated = 0
        inserted = 0
        for key, item in processed_items.items():
            report_date, subject_id = key
            data = item["data"]
            subject = item["subject"]
            rt = data["report_type"]
            report_period = self._get_report_period(report_date)
            ek = (report_date, subject_id, rt)
            existing = existing_map.get(ek)

            if existing:
                existing.value_decimal = data["value"]
                existing.subject_code = subject.code
                existing.report_period = report_period
                existing.data_source = "sina"
                updated += 1
            else:
                session.add(
                    FinancialData(
                        company_code=stock_code,
                        subject_id=subject_id,
                        subject_code=subject.code,
                        report_date=report_date,
                        report_type=ReportType(rt),
                        report_period=report_period,
                        value_decimal=data["value"],
                        data_source="sina",
                    )
                )
                inserted += 1

        await session.commit()
        logger.info(
            f"Saved {len(processed_items)} unique items for {stock_code} "
            f"(inserted={inserted}, updated={updated}, "
            f"matched_rows={matched_count}, unmatched_rows={unmatched_count})"
        )
        for rt, names in self._unmatched_names.items():
            if names:
                sample = sorted(names)[:12]
                logger.warning(
                    f"[Sina] 未匹配科目 {stock_code} {rt}: "
                    f"共{len(names)}个, 示例={sample}"
                )

    @staticmethod
    def _display_priority(display_type: Any) -> int:
        """display_type 越小优先级越高。主科目(2/6/1/7)优于明细(3)。"""
        try:
            dt = int(display_type) if display_type is not None else 99
        except (TypeError, ValueError):
            return 99
        # 汇总/主行优先
        if dt in (6, 7):
            return 1
        if dt == 2:
            return 2
        if dt == 1:
            return 3
        if dt == 3:
            return 5
        return 4

    def _match_quality(
        self,
        subject_name: str,
        subject: AccountSubject,
        display_type: Any,
        match_rank: int,
    ) -> tuple:
        """
        冲突消解质量分，越小越好。
        优先：精确标准名 > 含“合计/净额”的主行 > 别名命中 > display_type。
        """
        name = (subject_name or "").strip()
        exact = 0 if name == subject.name else 1
        sina_exact = 0 if subject.sina_name and name == subject.sina_name else 1
        # 合并行/合计行优先于“原值/净值/清理”等明细别名
        summary_bonus = 0
        if any(k in name for k in ("合计", "净额", "总计", "总额")):
            summary_bonus = 0
        elif any(k in name for k in ("原值", "清理", "减值准备", "累计折旧", "及")):
            summary_bonus = 2
        else:
            summary_bonus = 1
        return (
            match_rank,
            exact,
            sina_exact,
            summary_bonus,
            self._display_priority(display_type),
        )

    def _get_report_period(self, report_date: date) -> ReportPeriod:
        """根据报告日期确定报告期间"""
        month = report_date.month
        if month == 3:
            return ReportPeriod.Q1
        elif month == 6:
            return ReportPeriod.SEMI_ANNUAL
        elif month == 9:
            return ReportPeriod.Q3
        else:
            return ReportPeriod.ANNUAL

    async def _ensure_subject_cache(self, session) -> None:
        """加载科目与映射到内存索引，供匹配复用。"""
        if self._subject_cache_loaded:
            return

        result = await session.execute(select(AccountSubject))
        subjects = result.scalars().all()
        self._subjects_by_rt = {"BS": [], "IS": [], "CF": []}
        self._subjects_by_code = {}
        self._name_index = {"BS": {}, "IS": {}, "CF": {}}
        self._norm_index = {"BS": {}, "IS": {}, "CF": {}}

        for subject in subjects:
            rt = (
                subject.report_type.value
                if hasattr(subject.report_type, "value")
                else str(subject.report_type)
            )
            if rt not in self._subjects_by_rt:
                self._subjects_by_rt[rt] = []
            self._subjects_by_rt[rt].append(subject)
            self._subjects_by_code[subject.code] = subject

            if rt not in self._name_index:
                self._name_index[rt] = {}
                self._norm_index[rt] = {}

            self._name_index[rt][subject.name] = subject
            self._norm_index[rt][_normalize_subject_name(subject.name)] = subject
            if subject.sina_name:
                self._name_index[rt][subject.sina_name] = subject
                self._norm_index[rt][_normalize_subject_name(subject.sina_name)] = subject

        result = await session.execute(
            select(FinancialSubjectMapping).options(
                selectinload(FinancialSubjectMapping.standard_subject)
            )
        )
        mappings = result.scalars().all()
        self._mapping_by_name = {}
        for mapping in mappings:
            if mapping.financial_name and mapping.standard_subject:
                self._mapping_by_name[mapping.financial_name] = mapping.standard_subject
                self._mapping_by_name[_normalize_subject_name(mapping.financial_name)] = (
                    mapping.standard_subject
                )

        self._subject_cache_loaded = True
        logger.info(
            f"[Sina] 科目缓存加载完成: subjects={len(subjects)}, "
            f"mappings={len(self._mapping_by_name)}"
        )

    def _match_subject_cached(
        self,
        subject_name: str,
        report_type: str,
    ) -> Tuple[Optional[AccountSubject], int]:
        """
        匹配科目，返回 (subject, rank)。
        rank 越小优先级越高：
          0=别名表编码, 1=精确名, 2=sina_name/映射, 3=标准化名, 4=受控模糊
        """
        if not subject_name or subject_name in _SECTION_TITLES:
            return None, 99

        name = subject_name.strip()
        rt = report_type
        alias_code = SINA_SUBJECT_ALIASES.get(rt, {}).get(name)
        if not alias_code:
            # 也尝试标准化后的别名键
            norm_for_alias = _normalize_subject_name(name)
            for alias_name, code in SINA_SUBJECT_ALIASES.get(rt, {}).items():
                if _normalize_subject_name(alias_name) == norm_for_alias:
                    alias_code = code
                    break
        if alias_code and alias_code in self._subjects_by_code:
            return self._subjects_by_code[alias_code], 0

        name_idx = self._name_index.get(rt, {})
        if name in name_idx:
            return name_idx[name], 1

        if name in self._mapping_by_name:
            return self._mapping_by_name[name], 2

        norm = _normalize_subject_name(name)
        norm_idx = self._norm_index.get(rt, {})
        if norm and norm in norm_idx:
            return norm_idx[norm], 3
        if norm and norm in self._mapping_by_name:
            return self._mapping_by_name[norm], 2

        # 受控模糊：仅允许“去掉合计/净额等后缀”后的等价，或短名被标准名精确包含且长度接近
        best = None
        best_score = 0
        for subject in self._subjects_by_rt.get(rt, []):
            s_norm = _normalize_subject_name(subject.name)
            if not s_norm or not norm:
                continue
            if norm == s_norm:
                return subject, 3
            # 合计/净额/总额 后缀互认
            for suffix in ("合计", "净额", "总额", "余额"):
                if norm.rstrip(suffix) == s_norm or s_norm.rstrip(suffix) == norm:
                    return subject, 3
                if norm.endswith(suffix) and norm[: -len(suffix)] == s_norm:
                    return subject, 3
                if s_norm.endswith(suffix) and s_norm[: -len(suffix)] == norm:
                    return subject, 3

            # 仅当一方是另一方的真后缀/前缀，且较短方长度>=4，避免“利息收入”误伤
            if len(norm) >= 4 and len(s_norm) >= 4:
                if norm in s_norm or s_norm in norm:
                    shorter = min(len(norm), len(s_norm))
                    longer = max(len(norm), len(s_norm))
                    # 长度差过大不采纳（如 “其他综合收益” vs 很长子项）
                    if longer - shorter <= 6 and shorter / longer >= 0.7:
                        score = shorter / longer
                        if score > best_score:
                            best = subject
                            best_score = score

        if best is not None:
            return best, 4

        self._unmatched_names.setdefault(rt, set()).add(name)
        return None, 99

    async def _match_subject(self, session, subject_name: str, report_type: str) -> Optional[AccountSubject]:
        """兼容旧调用：确保缓存后走缓存匹配。"""
        await self._ensure_subject_cache(session)
        subject, _rank = self._match_subject_cached(subject_name, report_type)
        return subject

    async def crawl_stock_price(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        爬取股票历史价格

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            历史价格列表
        """
        # 简化实现
        # 实际需要调用新浪历史行情接口
        logger.info(f"Crawling stock price for {stock_code}")
        return []

    async def _fetch_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        使用新浪hq.sinajs.cn接口获取实时行情数据
        
        这个接口比HTML解析更简单、更可靠，返回格式为：
        var hq_str_sz000001="股票名称,开盘,昨收,现价,最高,最低,买一,卖一,成交量,成交额,..."
        var hq_str_sz000001_i="指标数据,包含PE、PB等"
        
        Args:
            stock_code: 股票代码
            
        Returns:
            包含价格等信息的字典，失败返回None
        """
        try:
            # 确定交易所前缀
            exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
            
            # 新浪综合行情API：获取实时行情、指标数据
            url = f"https://hq.sinajs.cn/rn={int(asyncio.get_event_loop().time())}&list={exchange_prefix}{stock_code},{exchange_prefix}{stock_code}_i"
            
            headers = {
                "Referer": f"https://finance.sina.com.cn/realstock/company/{exchange_prefix}{stock_code}/nc.shtml",
                "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36"
            }
            
            content = await self.fetch(url, headers=headers)
            if not content:
                return None
            
            # 解析返回的JavaScript格式数据
            # 有两行数据：实时行情、指标数据
            import re
            
            result = {
                'current_price': None,
                'open_price': None,
                'close_price': None,
                'high_price': None,
                'low_price': None,
                'volume': None,
                'amount': None,
                'market_cap': None,
                'pe_ratio': None,
                'pb_ratio': None,
            }
            
            # 1. 解析实时行情数据
            quote_match = re.search(r'var hq_str_[a-z]+[0-9]+="([^"]*)"', content)
            if quote_match:
                data_str = quote_match.group(1)
                if data_str:
                    fields = data_str.split(',')
                    if len(fields) >= 10:
                        # 0:股票名称, 1:开盘, 2:昨收, 3:现价, 4:最高, 5:最低, 8:成交量(手), 9:成交额(元)
                        try:
                            result['current_price'] = Decimal(fields[3]) if fields[3] else None
                            result['open_price'] = Decimal(fields[1]) if fields[1] else None
                            result['close_price'] = Decimal(fields[2]) if fields[2] else None
                            result['high_price'] = Decimal(fields[4]) if fields[4] else None
                            result['low_price'] = Decimal(fields[5]) if fields[5] else None
                            result['volume'] = Decimal(fields[8]) if fields[8] else None  # 手
                            result['amount'] = Decimal(fields[9]) if fields[9] else None  # 元
                        except Exception as e:
                            logger.warning(f"Error parsing quote fields: {e}")
            
            # 2. 解析指标数据（PE、PB等）
            # 格式：A,payh,每股收益,每股净资产,每股经营现金流,市净率,总股本,流通股本,总资产,净资产,营业收入...
            # 或者：A,market,每股收益,每股净资产,每股经营现金流,市盈率,市净率,总股本...
            indicator_match = re.search(r'var hq_str_[a-z]+[0-9]+_i="([^"]*)"', content)
            if indicator_match:
                data_str = indicator_match.group(1)
                if data_str:
                    fields = data_str.split(',')
                    if len(fields) >= 8:
                        try:
                            # 根据新浪接口的不同版本，PE和PB的位置可能不同
                            # 版本1: PE在位置5, PB在位置7
                            # 版本2: PE在位置21-22左右
                            
                            # 尝试从不同位置获取PE和PB
                            for i, field in enumerate(fields):
                                try:
                                    val = Decimal(field)
                                    # PE通常在5-50之间
                                    if 5 <= val <= 200 and not result['pe_ratio']:
                                        result['pe_ratio'] = val
                                    # PB通常在0.1-50之间
                                    if 0.1 <= val <= 50 and not result['pb_ratio'] and i > 4:
                                        result['pb_ratio'] = val
                                except:
                                    pass
                            
                            # 如果没有找到，尝试从固定位置获取
                            if not result['pe_ratio'] and len(fields) > 5:
                                try:
                                    val = Decimal(fields[5])
                                    if 5 <= val <= 200:
                                        result['pe_ratio'] = val
                                except:
                                    pass
                            
                            if not result['pb_ratio'] and len(fields) > 7:
                                try:
                                    val = Decimal(fields[7])
                                    if 0.1 <= val <= 50:
                                        result['pb_ratio'] = val
                                except:
                                    pass
                                    
                        except Exception as e:
                            logger.warning(f"Error parsing indicator fields: {e}")
            
            logger.info(f"Fetched comprehensive quote for {stock_code}: price={result['current_price']}, PE={result['pe_ratio']}, PB={result['pb_ratio']}")
            
            return result
                
        except Exception as e:
            logger.error(f"Error fetching real-time quote for {stock_code}: {e}")
            return None

    async def update_company_quotes(self, stock_code: str) -> bool:
        """
        更新公司行情信息 (实时)
        
        策略：优先使用 hq.sinajs.cn 接口（简单可靠），失败则回退到HTML页面解析。
        包含：当前价格、市值、市盈率、市净率、行业信息。
        """
        try:
            # 方法1: 使用新浪实时行情API（优先）
            quotes_data = await self._fetch_realtime_quote(stock_code)
            
            # 方法2: 如果API失败，尝试HTML页面解析（可以获取更多数据如PE、PB等）
            if not quotes_data or not quotes_data.get('current_price'):
                logger.warning(f"Real-time API failed for {stock_code}, trying HTML parsing...")
                
                # 1. Determine exchange prefix
                exchange_prefix = "sz" if stock_code.startswith(("0", "3")) else "sh"
                
                # URL 1: HTML Page
                url = f"https://finance.sina.com.cn/realstock/company/{exchange_prefix}{stock_code}/nc.shtml"
                
                headers = {
                    "Referer": "https://finance.sina.com.cn/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                content = await self.fetch(url, headers=headers)
                
                # If HTML fetch fails
                if not content:
                    logger.warning(f"Failed to fetch quotes from HTML for {stock_code}")
                    return False
                    
                # 2. Parse Data
                quotes_data = self._parse_html_quotes(content, stock_code)
                
                if not quotes_data:
                    logger.warning(f"Failed to parse quotes data for {stock_code}")
                    return False
                    
            # 3. Update DB
            async with async_session_factory() as session:
                stmt = select(Company).where(Company.stock_code == stock_code)
                result = await session.execute(stmt)
                company = result.scalars().first()
                
                if not company:
                    logger.error(f"Company {stock_code} not found for update")
                    return False
                
                updated = False
                
                # Update basic quotes
                if quotes_data.get('current_price'):
                    company.current_price = quotes_data['current_price']
                    updated = True
                
                if quotes_data.get('pe_ratio'):
                    company.pe_ratio = quotes_data['pe_ratio']
                    updated = True
                    
                if quotes_data.get('pb_ratio'):
                    company.pb_ratio = quotes_data['pb_ratio']
                    updated = True
                    
                if quotes_data.get('market_cap'):
                    company.market_cap = quotes_data['market_cap']
                    updated = True
                
                # Update Industry
                industry_name = quotes_data.get('industry')
                if industry_name:
                    # Find or convert industry
                    stmt = select(Industry).where(Industry.name == industry_name)
                    result = await session.execute(stmt)
                    industry = result.scalars().first()
                    
                    if not industry:
                        # Create new industry
                        # Generate a simple code if possible, or use uuid/random? 
                        # Ideally assume industry codes are standard, but here we just have name.
                        # We can generate a code based on hash or just use auto-increment ID if code is not strict
                        import hashlib
                        code_hash = hashlib.md5(industry_name.encode('utf-8')).hexdigest()[:8].upper()
                        
                        industry = Industry(
                            code=f"IND_{code_hash}",
                            name=industry_name,
                            is_active=True
                        )
                        session.add(industry)
                        await session.flush() # flush to get ID
                        logger.info(f"Created new industry: {industry_name}")
                    
                    if company.industry_id != industry.id:
                        company.industry_id = industry.id
                        updated = True

                if updated:
                    await session.commit()
                    logger.info(f"Updated quotes for {stock_code}: Price={company.current_price}, PE={company.pe_ratio}, Industry={industry_name}")
                    return True
                else:
                    logger.info(f"No updates found for {stock_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating quotes for {stock_code}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _parse_html_quotes(self, html_content: str, stock_code: str) -> Optional[Dict[str, Any]]:
        """Parses HTML content for quote data (Price, PE, PB, MarketCap, Industry)"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            quotes_data = {
                'current_price': None,
                'market_cap': None,
                'pe_ratio': None,
                'pb_ratio': None,
                'industry': None
            }
            
            all_text = soup.get_text()
            
            # --- 1. Current Price ---
            # 新浪财经的实时价格通常在特定的元素中
            # 查找包含价格的元素
            price_found = False
            
            # 方法1: 查找包含价格的span或div元素
            price_elements = soup.find_all(['span', 'div'], string=re.compile(r'[\d.]+'))
            for el in price_elements:
                text = el.get_text(strip=True)
                # 检查是否是价格（通常格式为数字，可能有货币符号）
                # 排除明显不是价格的情况（如日期、年份等）
                if re.match(r'^\d+\.\d+$', text):
                    # 检查是否在合理的价格范围内（0.01 - 10000）
                    try:
                        price = Decimal(text)
                        if 0.01 <= price <= 10000:
                            # 检查上下文是否与股票相关
                            parent = el.parent
                            if parent:
                                parent_text = parent.get_text()
                                # 如果父元素包含"价格"、"现价"、"最新"等关键词
                                if any(keyword in parent_text for keyword in ['价格', '现价', '最新', 'Price', 'Last']):
                                    quotes_data['current_price'] = price
                                    price_found = True
                                    break
                    except:
                        pass
                if price_found:
                    break

            # --- 2. PE Ratio ---
            pe_patterns = [
                r'市盈率\(动态\)[：:\s]*(\d+\.?\d*)',
                r'市盈率[：:\s]*(\d+\.?\d*)',
                r'PE[：:\s]*(\d+\.?\d*)',
            ]
            for pattern in pe_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        pe = Decimal(match.group(1))
                        if 0 < pe < 2000:
                            quotes_data['pe_ratio'] = pe
                            break
                    except:
                        pass

            # --- 3. PB Ratio ---
            pb_patterns = [
                r'市净率[：:\s]*(\d+\.?\d*)',
                r'PB[：:\s]*(\d+\.?\d*)',
            ]
            for pattern in pb_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        pb = Decimal(match.group(1))
                        if 0 < pb < 200:
                            quotes_data['pb_ratio'] = pb
                            break
                    except:
                        pass
                        
            # --- 4. Market Cap ---
            # Handles units like 亿, 万
            mc_patterns = [
                r'市值[：:\s]*(\d+\.?\d*)\s*(亿|万|元)',
                r'总市值[：:\s]*(\d+\.?\d*)\s*(亿|万|元)',
            ]
            for pattern in mc_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        val = Decimal(match.group(1))
                        unit = match.group(2)
                        
                        multiplier = 1
                        if unit == '亿':
                            multiplier = 10000 # Store in "Wan" (Ten Thousand) as per model comment "总市值(万元)"? 
                            # Model comment says: "总市值(万元)"
                            # '亿' = 10^8. '万' = 10^4.
                            # So 1 亿 = 10000 万. 
                        elif unit == '万':
                            multiplier = 1 
                        elif unit == '元':
                            multiplier = Decimal('0.0001')
                            
                        quotes_data['market_cap'] = val * multiplier
                        break
                    except:
                        pass

            # --- 5. Industry ---
            ind_patterns = [
                r'所属行业[：:\s]*([^,\n\r\t\s]+)',
                r'行业[：:\s]*([^,\n\r\t\s]+)',
                r'所属板块[：:\s]*([^,\n\r\t\s]+)',
            ]
            for pattern in ind_patterns:
                match = re.search(pattern, all_text)
                if match:
                    ind = match.group(1).strip()
                    # Filter out noise
                    if 1 < len(ind) < 20 and '净率' not in ind and '盈率' not in ind:
                         quotes_data['industry'] = ind
                         break
            
            # Debug logging
            logger.info(f"Parsed quotes for {stock_code}: {quotes_data}")
            return quotes_data

        except Exception as e:
            logger.warning(f"Error parsing HTML quotes for {stock_code}: {e}")
            return None

