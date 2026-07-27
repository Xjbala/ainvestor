# -*- coding: utf-8 -*-
"""
交易所官方数据采集服务
从深圳证券交易所和上海证券交易所官方API采集公司数据。
移植自 leofun 项目，适配 ainvestor 异步架构。
"""

import logging
import asyncio
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import CrawlerService, parse_decimal
from ..persistence.db import async_session_factory
from ..persistence.financial_models import Company, Exchange, Industry, CompanyStatus

logger = logging.getLogger(__name__)


class ExchangeCrawler(CrawlerService):
    """
    交易所官方数据采集服务
    """

    def __init__(self, session: AsyncSession, **kwargs):
        super().__init__(session, data_source_code="exchange_api", **kwargs)
        self.szse_base_url = 'http://www.szse.cn'
        self.szse_api_base = 'http://www.szse.cn/api'
        self.sse_base_url = 'http://query.sse.com.cn'

    async def crawl_company_list(self) -> List[Dict[str, Any]]:
        """
        实现基类方法，默认同步所有交易所
        """
        return await self.sync_companies_from_exchanges()

    async def sync_companies_from_exchanges(self, exchanges: List[str] = None) -> List[Dict[str, Any]]:
        """
        从交易所同步公司数据
        
        Args:
            exchanges: 指定交易所列表，如 ['SSE', 'SZSE']
            
        Returns:
            所有抓取到的公司数据列表
        """
        if exchanges is None:
            exchanges = ['SSE', 'SZSE']

        all_companies = []
        
        # 独立处理每个交易所，确保互不影响
        if 'SZSE' in exchanges:
            try:
                szse_companies = await self._crawl_szse()
                if szse_companies:
                    await self.save_companies(szse_companies)
                    all_companies.extend(szse_companies)
                    logger.info("SZSE sync completed and saved.")
            except Exception as e:
                logger.error(f"Failed to sync SZSE: {e}", exc_info=True)
            
        if 'SSE' in exchanges:
            try:
                sse_companies = await self._crawl_sse()
                if sse_companies:
                    await self.save_companies(sse_companies)
                    all_companies.extend(sse_companies)
                    logger.info("SSE sync completed and saved.")
            except Exception as e:
                logger.error(f"Failed to sync SSE: {e}", exc_info=True)

        return all_companies

    async def _crawl_szse(self) -> List[Dict[str, Any]]:
        """抓取深交所数据"""
        companies = []
        seen_codes = set()
        
        # 1: 主板A股, 2: 中小板 (现在并入主板), 3: 创业板
        # 注意：深交所现在其实主要是 1 和 3
        market_types = [
            {'tab': '1', 'name': '主板'},
            {'tab': '3', 'name': '创业板'}
        ]

        headers = {
            'Host': 'www.szse.cn',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'http://www.szse.cn/market/product/stock/list/index.html',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        for market in market_types:
            logger.info(f"Crawling SZSE {market['name']}...")
            tab = market['tab']
            page_size = 50
            
            # 获取总页数
            try:
                total_pages = await self._get_szse_total_pages(tab, page_size, headers)
            except Exception as e:
                logger.error(f"Failed to get SZSE total pages for {market['name']}: {e}")
                continue

            if not total_pages:
                continue

            for page in range(1, total_pages + 1):
                logger.info(f"SZSE {market['name']} Page {page}/{total_pages}")
                url = f"{self.szse_api_base}/report/ShowReport/data"
                params = {
                    'SHOWTYPE': 'JSON',
                    'CATALOGID': '1110',
                    'TABKEY': f'tab{tab}',
                    'random': str(Decimal(datetime.now().timestamp() * 1000).quantize(Decimal('1'))),
                    'PAGENO': page,
                    'PAGESIZE': page_size
                }
                
                try:
                    data = await self.fetch_json(url, headers=headers, params=params)
                    if not data or not isinstance(data, list):
                        continue

                    # 提取对应 tab 的数据
                    target_data = next((item for item in data if isinstance(item, dict) and item.get('metadata', {}).get('tabkey') == f'tab{tab}'), None)
                    if not target_data:
                        continue

                    records = target_data.get('data', [])
                    for record in records:
                        company = self._parse_szse_record(record)
                        if company and company['stock_code'] not in seen_codes:
                            seen_codes.add(company['stock_code'])
                            companies.append(company)
                    
                    await asyncio.sleep(1) # 礼貌抓取
                except Exception as e:
                    logger.error(f"Error crawling SZSE page {page}: {e}")
                    continue
                
        logger.info(f"SZSE total: {len(companies)}")
        return companies

    async def _get_szse_total_pages(self, tab: str, page_size: int, headers: dict) -> Optional[int]:
        url = f"{self.szse_api_base}/report/ShowReport/data"
        params = {
            'SHOWTYPE': 'JSON',
            'CATALOGID': '1110',
            'TABKEY': f'tab{tab}',
            'random': str(Decimal(datetime.now().timestamp() * 1000).quantize(Decimal('1'))),
            'PAGENO': 1,
            'PAGESIZE': page_size
        }
        data = await self.fetch_json(url, headers=headers, params=params)
        if not data or not isinstance(data, list):
            return None
            
        target_data = next((item for item in data if isinstance(item, dict) and item.get('metadata', {}).get('tabkey') == f'tab{tab}'), None)
        if not target_data:
            return None
            
        return target_data.get('metadata', {}).get('pagecount')

    def _parse_szse_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # A股代码或B股代码
        stock_code = record.get('agdm', '').strip() or record.get('bgdm', '').strip()
        stock_name_raw = record.get('agjc', '').strip() or record.get('bgjc', '').strip()
        listing_date_str = record.get('agssrq', '').strip() or record.get('bgssrq', '').strip()
        
        if not stock_code:
            return None
            
        # 去除 HTML 标签
        stock_name = re.sub(r'<[^>]+>', '', stock_name_raw)
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'company_name': stock_name,
            'exchange': 'SZSE',
            'industry': record.get('sshymc', '').strip(),
            'listing_date': self._parse_date(listing_date_str),
            'data_source': 'SZSE_OFFICIAL'
        }

    async def _crawl_sse(self) -> List[Dict[str, Any]]:
        """抓取上交所数据"""
        companies = []
        # 1: 主板, 8: 科创板
        # 参考用户提供的URL，STOCK_TYPE=1 为主板
        # http://query.sse.com.cn/sseQuery/commonQuery.do?jsonCallBack=jsonpCallback12409598&STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&isPagination=true&pageHelp.cacheSize=1&pageHelp.beginPage=1&pageHelp.pageSize=25&pageHelp.pageNo=1&pageHelp.endPage=1&_=1769782773659
        
        stock_types = [
            {'type': '1', 'name': '主板'},
            {'type': '8', 'name': '科创板'}
        ]

        # 更新Headers，SSE对referer检查较严
        headers = {
            'Referer': 'http://www.sse.com.cn/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': '*/*'
        }

        for st in stock_types:
            logger.info(f"Crawling SSE {st['name']}...")
            page = 1
            page_size = 100
            
            while True:
                url = f"{self.sse_base_url}/sseQuery/commonQuery.do"
                # 构造符合用户提供的参数结构
                callback_name = f"jsonpCallback{int(datetime.now().timestamp() * 1000)}"
                params = {
                    'jsonCallBack': callback_name,
                    'STOCK_TYPE': st['type'],
                    'REG_PROVINCE': '',
                    'CSRC_CODE': '',
                    'STOCK_CODE': '',
                    'sqlId': 'COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L',
                    'COMPANY_STATUS': '2,4,5,7,8',
                    'type': 'inParams',
                    'isPagination': 'true',
                    'pageHelp.cacheSize': '1',
                    'pageHelp.beginPage': page,
                    'pageHelp.pageSize': page_size,
                    'pageHelp.pageNo': page,
                    'pageHelp.endPage': page,
                    '_': str(int(datetime.now().timestamp() * 1000))
                }
                
                try:
                    # SSE 返回的是 JSONP，不能直接用 fetch_json
                    response_text = await self.fetch(url, headers=headers, params=params)
                    if not response_text:
                        break
                    
                    # 解析 JSONP: jsonpCallback123({...}) -> {...}
                    match = re.search(r'jsonpCallback\d+\((.*)\)', response_text, re.DOTALL)
                    if not match:
                        logger.warning(f"Failed to parse JSONP response from SSE: {response_text[:100]}")
                        break
                        
                    import json
                    try:
                        data = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        logger.error("Failed to decode SSE JSON")
                        break

                    if not data or 'result' not in data:
                        break
                        
                    records = data['result']
                    if not records:
                        break
                        
                    for record in records:
                        companies.append({
                            'stock_code': record.get('A_STOCK_CODE', '').strip(),
                            'stock_name': record.get('COMPANY_ABBR', '').strip(),
                            'company_name': record.get('FULL_NAME', '').strip(),
                            'exchange': 'SSE',
                            'listing_date': self._parse_date(record.get('LIST_DATE', '')),
                            'market_cap': parse_decimal(record.get('MARKET_CAP')),
                            'current_price': parse_decimal(record.get('PREV_CLOSE')),
                            'data_source': 'SSE_OFFICIAL'
                        })
                    
                    # 检查是否还有下一页
                    total_records = data.get('pageHelp', {}).get('total', 0)
                    if page * page_size >= total_records:
                        break
                    
                    page += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error crawling SSE page {page}: {e}")
                    break

        logger.info(f"SSE total: {len(companies)}")
        return companies

    def _parse_date(self, date_str: str) -> Optional[date]:
        if not date_str:
            return None
        try:
            for fmt in ['%Y-%m-%d', '%Y%m%d', '%Y.%m.%d']:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    async def save_companies(self, companies: List[Dict[str, Any]]):
        """保存公司列表到数据库 (异步版)"""
        if not companies:
            return
            
        async with async_session_factory() as session:
            # 1. 确保交易所存在
            exchange_map = {}
            for code in ['SSE', 'SZSE']:
                stmt = select(Exchange).where(Exchange.code == code)
                res = await session.execute(stmt)
                ex = res.scalar_one_or_none()
                if not ex:
                    name = "上海证券交易所" if code == 'SSE' else "深圳证券交易所"
                    ex = Exchange(code=code, name=name, country="中国")
                    session.add(ex)
                    await session.flush()
                exchange_map[code] = ex.id

            # 2. 批量处理公司更新/创建
            for item in companies:
                stock_code = item['stock_code']
                stmt = select(Company).where(Company.stock_code == stock_code)
                res = await session.execute(stmt)
                company = res.scalar_one_or_none()
                
                if company:
                    # 更新现有公司信息
                    company.stock_name = item.get('stock_name', company.stock_name)
                    company.company_name = item.get('company_name', company.company_name)
                    company.listing_date = item.get('listing_date', company.listing_date)
                    if item.get('market_cap'):
                        company.market_cap = item['market_cap']
                    if item.get('current_price'):
                        company.current_price = item['current_price']
                else:
                    # 创建新公司
                    company = Company(
                        stock_code=stock_code,
                        stock_name=item.get('stock_name'),
                        company_name=item.get('company_name'),
                        exchange_id=exchange_map.get(item['exchange']),
                        listing_date=item.get('listing_date'),
                        current_price=item.get('current_price'),
                        market_cap=item.get('market_cap'),
                        status=CompanyStatus.ACTIVE
                    )
                    session.add(company)
            
            await session.commit()
            logger.info(f"Saved {len(companies)} companies to database")

    async def crawl_financial_report(self, stock_code: str, report_type: str, year: int) -> Optional[Dict[str, Any]]:
        """Exchange API 通常不直接提供标准化的财务外报，由 SinaCrawler 处理"""
        return None
