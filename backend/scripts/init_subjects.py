import asyncio
import sys
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.persistence.db import async_session_factory, engine, init_database
from backend.persistence.financial_models import AccountCategory, AccountSubject, ReportType, SubjectCategory, DataType

async def init_subjects():
    # 确保数据库表已创建
    await init_database()
    
    async with async_session_factory() as session:
        print("开始初始化科目数据...")
        
        # 1. 创建科目分类
        categories_data = [
            # 资产负债表分类
            {'code': 'BS_ASSETS', 'name': '资产', 'report_type': ReportType.BS, 'level': 1, 'sort_order': 10},
            {'code': 'BS_CURRENT_ASSETS', 'name': '流动资产', 'report_type': ReportType.BS, 'level': 2, 'sort_order': 11, 'parent_code': 'BS_ASSETS'},
            {'code': 'BS_NON_CURRENT_ASSETS', 'name': '非流动资产', 'report_type': ReportType.BS, 'level': 2, 'sort_order': 12, 'parent_code': 'BS_ASSETS'},
            {'code': 'BS_LIABILITIES', 'name': '负债', 'report_type': ReportType.BS, 'level': 1, 'sort_order': 20},
            {'code': 'BS_CURRENT_LIABILITIES', 'name': '流动负债', 'report_type': ReportType.BS, 'level': 2, 'sort_order': 21, 'parent_code': 'BS_LIABILITIES'},
            {'code': 'BS_NON_CURRENT_LIABILITIES', 'name': '非流动负债', 'report_type': ReportType.BS, 'level': 2, 'sort_order': 22, 'parent_code': 'BS_LIABILITIES'},
            {'code': 'BS_EQUITY', 'name': '所有者权益', 'report_type': ReportType.BS, 'level': 1, 'sort_order': 30},
            
            # 利润表分类
            {'code': 'IS_REVENUE', 'name': '营业收入', 'report_type': ReportType.IS, 'level': 1, 'sort_order': 10},
            {'code': 'IS_COSTS', 'name': '营业成本', 'report_type': ReportType.IS, 'level': 1, 'sort_order': 20},
            {'code': 'IS_EXPENSES', 'name': '期间费用', 'report_type': ReportType.IS, 'level': 1, 'sort_order': 30},
            {'code': 'IS_OTHER_INCOME', 'name': '其他收益', 'report_type': ReportType.IS, 'level': 1, 'sort_order': 40},
            
            # 现金流量表分类
            {'code': 'CF_OPERATING', 'name': '经营活动现金流量', 'report_type': ReportType.CF, 'level': 1, 'sort_order': 10},
            {'code': 'CF_INVESTING', 'name': '投资活动现金流量', 'report_type': ReportType.CF, 'level': 1, 'sort_order': 20},
            {'code': 'CF_FINANCING', 'name': '筹资活动现金流量', 'report_type': ReportType.CF, 'level': 1, 'sort_order': 30},
        ]

        category_map = {}
        for data in categories_data:
            parent_code = data.pop('parent_code', None)
            stmt = select(AccountCategory).where(AccountCategory.code == data['code'])
            result = await session.execute(stmt)
            category = result.scalar_one_or_none()
            
            if not category:
                category = AccountCategory(**data)
                session.add(category)
                await session.flush()
                print(f"创建分类: {category.name}")
            
            category_map[data['code']] = category.id
            
            if parent_code and parent_code in category_map:
                category.parent_id = category_map[parent_code]

        await session.commit()

        # 2. 创建标准科目
        subjects_data = [
            # ========== 合并资产负债表科目 ==========
            # 一、流动资产
            {'code': 'BSA001', 'name': '货币资金', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 1},
            {'code': 'BSA002', 'name': '结算备付金', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 2},
            {'code': 'BSA003', 'name': '拆出资金', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 3},
            {'code': 'BSA004', 'name': '交易性金融资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 4},
            {'code': 'BSA005', 'name': '衍生金融资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 5},
            {'code': 'BSA006', 'name': '应收票据', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 6},
            {'code': 'BSA007', 'name': '应收账款', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 7},
            {'code': 'BSA008', 'name': '应收款项融资', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 8},
            {'code': 'BSA009', 'name': '预付款项', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 9},
            {'code': 'BSA010', 'name': '应收保费', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 10},
            {'code': 'BSA011', 'name': '应收分保账款', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 11},
            {'code': 'BSA012', 'name': '应收分保合同准备金', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 12},
            {'code': 'BSA013', 'name': '其他应收款', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 13},
            {'code': 'BSA014', 'name': '买入返售金融资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 14},
            {'code': 'BSA015', 'name': '存货', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 15},
            {'code': 'BSA016', 'name': '合同资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 16},
            {'code': 'BSA017', 'name': '持有待售资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 17},
            {'code': 'BSA018', 'name': '一年内到期的非流动资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 18},
            {'code': 'BSA019', 'name': '其他流动资产', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 19},
            {'code': 'BSA020', 'name': '流动资产合计', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'is_summary': True, 'sort_order': 20},
            {'code': 'BSA021', 'name': '应收股利', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 13},
            {'code': 'BSA022', 'name': '应收利息', 'category_code': 'BS_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 14},
            
            # 二、非流动资产
            {'code': 'BSA101', 'name': '发放贷款和垫款', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 101},
            {'code': 'BSA102', 'name': '债权投资', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 102},
            {'code': 'BSA103', 'name': '其他债权投资', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 103},
            {'code': 'BSA104', 'name': '长期应收款', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 104},
            {'code': 'BSA105', 'name': '长期股权投资', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 105},
            {'code': 'BSA106', 'name': '其他权益工具投资', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 106},
            {'code': 'BSA107', 'name': '其他非流动金融资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 107},
            {'code': 'BSA108', 'name': '投资性房地产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 108},
            {'code': 'BSA109', 'name': '固定资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 109},
            {'code': 'BSA110', 'name': '在建工程', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 110},
            {'code': 'BSA111', 'name': '生产性生物资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 111},
            {'code': 'BSA112', 'name': '油气资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 112},
            {'code': 'BSA113', 'name': '使用权资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 113},
            {'code': 'BSA114', 'name': '无形资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 114},
            {'code': 'BSA115', 'name': '开发支出', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 115},
            {'code': 'BSA116', 'name': '商誉', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 116},
            {'code': 'BSA117', 'name': '长期待摊费用', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 117},
            {'code': 'BSA118', 'name': '递延所得税资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 118},
            {'code': 'BSA119', 'name': '其他非流动资产', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'sort_order': 119},
            {'code': 'BSA120', 'name': '非流动资产合计', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'is_summary': True, 'sort_order': 120},
            {'code': 'BSA121', 'name': '资产总计', 'category_code': 'BS_NON_CURRENT_ASSETS', 'report_type': ReportType.BS, 'subject_category': 'A', 'is_summary': True, 'sort_order': 121},

            # 三、流动负债
            {'code': 'BSL001', 'name': '短期借款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 1},
            {'code': 'BSL002', 'name': '向中央银行借款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 2},
            {'code': 'BSL003', 'name': '拆入资金', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 3},
            {'code': 'BSL004', 'name': '交易性金融负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 4},
            {'code': 'BSL005', 'name': '衍生金融负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 5},
            {'code': 'BSL006', 'name': '应付票据', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 6},
            {'code': 'BSL007', 'name': '应付账款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 7},
            {'code': 'BSL008', 'name': '预收款项', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 8},
            {'code': 'BSL009', 'name': '合同负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 9},
            {'code': 'BSL010', 'name': '卖出回购金融资产款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 10},
            {'code': 'BSL011', 'name': '吸收存款及同业存放', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 11},
            {'code': 'BSL012', 'name': '代理买卖证券款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 12},
            {'code': 'BSL013', 'name': '代理承销证券款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 13},
            {'code': 'BSL014', 'name': '应付职工薪酬', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 14},
            {'code': 'BSL015', 'name': '应交税费', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 15},
            {'code': 'BSL016', 'name': '其他应付款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 16},
            {'code': 'BSL017', 'name': '应付手续费及佣金', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 17},
            {'code': 'BSL018', 'name': '应付分保账款', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 18},
            {'code': 'BSL019', 'name': '持有待售负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 19},
            {'code': 'BSL020', 'name': '一年内到期的非流动负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 20},
            {'code': 'BSL021', 'name': '其他流动负债', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 21},
            {'code': 'BSL022', 'name': '流动负债合计', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'is_summary': True, 'sort_order': 22},
            {'code': 'BSL023', 'name': '应付股利', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 16},
            {'code': 'BSL024', 'name': '应付利息', 'category_code': 'BS_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 17},

            # 四、非流动负债
            {'code': 'BSL101', 'name': '保险合同准备金', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 101},
            {'code': 'BSL102', 'name': '长期借款', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 102},
            {'code': 'BSL103', 'name': '应付债券', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 103},
            {'code': 'BSL104', 'name': '租赁负债', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 104},
            {'code': 'BSL105', 'name': '长期应付款', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 105},
            {'code': 'BSL106', 'name': '长期应付职工薪酬', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 106},
            {'code': 'BSL107', 'name': '预计负债', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 107},
            {'code': 'BSL108', 'name': '递延收益', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 108},
            {'code': 'BSL109', 'name': '递延所得税负债', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 109},
            {'code': 'BSL110', 'name': '其他非流动负债', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'sort_order': 110},
            {'code': 'BSL111', 'name': '非流动负债合计', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'is_summary': True, 'sort_order': 111},
            {'code': 'BSL112', 'name': '负债合计', 'category_code': 'BS_NON_CURRENT_LIABILITIES', 'report_type': ReportType.BS, 'subject_category': 'L', 'is_summary': True, 'sort_order': 112},

            # 五、所有者权益
            {'code': 'BSE001', 'name': '实收资本（或股本）', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 1},
            {'code': 'BSE002', 'name': '其他权益工具', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 2},
            {'code': 'BSE003', 'name': '资本公积', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 3},
            {'code': 'BSE004', 'name': '库存股', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 4},
            {'code': 'BSE005', 'name': '其他综合收益', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 5},
            {'code': 'BSE006', 'name': '专项储备', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 6},
            {'code': 'BSE007', 'name': '盈余公积', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 7},
            {'code': 'BSE008', 'name': '一般风险准备', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 8},
            {'code': 'BSE009', 'name': '未分配利润', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 9},
            {'code': 'BSE010', 'name': '归属于母公司所有者权益合计', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'is_summary': True, 'sort_order': 10},
            {'code': 'BSE011', 'name': '少数股东权益', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'sort_order': 11},
            {'code': 'BSE012', 'name': '所有者权益（或股东权益）合计', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'is_summary': True, 'sort_order': 12},
            {'code': 'BSE013', 'name': '负债和所有者权益（或股东权益）总计', 'category_code': 'BS_EQUITY', 'report_type': ReportType.BS, 'subject_category': 'E', 'is_summary': True, 'sort_order': 13},

            # ========== 合并利润表科目 ==========
            # 一、营业总收入
            {'code': 'ISI001', 'name': '营业收入', 'category_code': 'IS_REVENUE', 'report_type': ReportType.IS, 'subject_category': 'I', 'sort_order': 1},
            {'code': 'ISI002', 'name': '利息收入', 'category_code': 'IS_REVENUE', 'report_type': ReportType.IS, 'subject_category': 'I', 'sort_order': 2},
            {'code': 'ISI003', 'name': '已赚保费', 'category_code': 'IS_REVENUE', 'report_type': ReportType.IS, 'subject_category': 'I', 'sort_order': 3},
            {'code': 'ISI004', 'name': '手续费及佣金收入', 'category_code': 'IS_REVENUE', 'report_type': ReportType.IS, 'subject_category': 'I', 'sort_order': 4},
            {'code': 'ISI005', 'name': '营业总收入', 'category_code': 'IS_REVENUE', 'report_type': ReportType.IS, 'subject_category': 'I', 'is_summary': True, 'sort_order': 5},
            
            # 二、营业总成本
            {'code': 'ISC001', 'name': '营业成本', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 1},
            {'code': 'ISC002', 'name': '利息支出', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 2},
            {'code': 'ISC003', 'name': '手续费及佣金支出', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 3},
            {'code': 'ISC004', 'name': '退保金', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 4},
            {'code': 'ISC005', 'name': '赔付支出净额', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 5},
            {'code': 'ISC006', 'name': '提取保险合同准备金净额', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 6},
            {'code': 'ISC007', 'name': '保单红利支出', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 7},
            {'code': 'ISC008', 'name': '分保费用', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 8},
            {'code': 'ISC009', 'name': '营业税金及附加', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'sort_order': 9},
            {'code': 'ISC010', 'name': '营业总成本', 'category_code': 'IS_COSTS', 'report_type': ReportType.IS, 'subject_category': 'C', 'is_summary': True, 'sort_order': 10},
            
            # 三、营业利润
            {'code': 'ISF001', 'name': '销售费用', 'category_code': 'IS_EXPENSES', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 1},
            {'code': 'ISF002', 'name': '管理费用', 'category_code': 'IS_EXPENSES', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 2},
            {'code': 'ISF003', 'name': '研发费用', 'category_code': 'IS_EXPENSES', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 3},
            {'code': 'ISF004', 'name': '财务费用', 'category_code': 'IS_EXPENSES', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 4},
            {'code': 'ISF016', 'name': '营业利润', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'is_summary': True, 'sort_order': 16},
            
            # 四利润总额
            {'code': 'ISF019', 'name': '利润总额', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'is_summary': True, 'sort_order': 19},
            
            # 五、净利润
            {'code': 'ISF021', 'name': '净利润', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'is_summary': True, 'sort_order': 21},
            {'code': 'ISF023', 'name': '持续经营净利润', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 23},
            {'code': 'ISF024', 'name': '终止经营净利润', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 24},
            {'code': 'ISF026', 'name': '归属于母公司所有者的净利润', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 26},
            {'code': 'ISF027', 'name': '少数股东损益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 27},
            {'code': 'ISF028', 'name': '资产减值损失', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 14},
            {'code': 'ISE001', 'name': '基本每股收益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 40},
            {'code': 'ISE002', 'name': '稀释每股收益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 41},
            {'code': 'ISO001', 'name': '其他综合收益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 30},
            {'code': 'ISO002', 'name': '归属于母公司所有者的其他综合收益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 31},
            {'code': 'ISO003', 'name': '归属于少数股东的其他综合收益', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 32},
            {'code': 'ISO004', 'name': '综合收益总额', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'is_summary': True, 'sort_order': 33},
            {'code': 'ISO005', 'name': '归属于母公司所有者的综合收益总额', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 34},
            {'code': 'ISO006', 'name': '归属于少数股东的综合收益总额', 'category_code': 'IS_OTHER_INCOME', 'report_type': ReportType.IS, 'subject_category': 'F', 'sort_order': 35},

            # ========== 合并现金流量表科目 ==========
            # 一、经营活动
            {'code': 'CFO001', 'name': '销售商品、提供劳务收到的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 1},
            {'code': 'CFO002', 'name': '客户存款和同业存放款项净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 2},
            {'code': 'CFO003', 'name': '向中央银行借款净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 3},
            {'code': 'CFO004', 'name': '向其他金融机构拆入资金净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 4},
            {'code': 'CFO005', 'name': '收取利息、手续费及佣金的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 5},
            {'code': 'CFO006', 'name': '拆入资金净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 6},
            {'code': 'CFO007', 'name': '回购业务资金净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 7},
            {'code': 'CFO008', 'name': '代理买卖证券收到的现金净额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 8},
            {'code': 'CFO009', 'name': '收到的税费返还', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 9},
            {'code': 'CFO010', 'name': '收到其他与经营活动有关的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 10},
            {'code': 'CFO011', 'name': '经营活动现金流入小计', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'is_summary': True, 'sort_order': 11},
            {'code': 'CFO012', 'name': '购买商品、接受劳务支付的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 12},
            {'code': 'CFO013', 'name': '客户贷款及垫款净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 13},
            {'code': 'CFO014', 'name': '存放中央银行和同业款项净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 14},
            {'code': 'CFO015', 'name': '支付利息、手续费及佣金的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 15},
            {'code': 'CFO016', 'name': '支付给职工以及为职工支付的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 16},
            {'code': 'CFO017', 'name': '支付的各项税费', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 17},
            {'code': 'CFO018', 'name': '支付其他与经营活动有关的现金', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 18},
            {'code': 'CFO019', 'name': '经营活动现金流出小计', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'is_summary': True, 'sort_order': 19},
            {'code': 'CFO020', 'name': '经营活动产生的现金流量净额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'is_summary': True, 'sort_order': 20},

            # 二、投资活动
            {'code': 'CFIV001', 'name': '收回投资收到的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 1},
            {'code': 'CFIV002', 'name': '取得投资收益收到的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 2},
            {'code': 'CFIV003', 'name': '处置固定资产、无形资产和其他长期资产收回的现金净额', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 3},
            {'code': 'CFIV004', 'name': '处置子公司及其他营业单位收到的现金净额', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 4},
            {'code': 'CFIV005', 'name': '收到其他与投资活动有关的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 5},
            {'code': 'CFIV006', 'name': '投资活动现金流入小计', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'is_summary': True, 'sort_order': 6},
            {'code': 'CFIV007', 'name': '购建固定资产、无形资产和其他长期资产支付的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 7},
            {'code': 'CFIV008', 'name': '投资支付的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 8},
            {'code': 'CFIV009', 'name': '取得子公司及其他营业单位支付的现金净额', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 9},
            {'code': 'CFIV010', 'name': '支付其他与投资活动有关的现金', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'sort_order': 10},
            {'code': 'CFIV011', 'name': '投资活动现金流出小计', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'is_summary': True, 'sort_order': 11},
            {'code': 'CFIV012', 'name': '投资活动产生的现金流量净额', 'category_code': 'CF_INVESTING', 'report_type': ReportType.CF, 'subject_category': 'IV', 'is_summary': True, 'sort_order': 12},

            # 三、筹资活动
            {'code': 'CFFN001', 'name': '吸收投资收到的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 1},
            {'code': 'CFFN002', 'name': '其中：子公司吸收少数股东投资收到的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 2},
            {'code': 'CFFN003', 'name': '取得借款收到的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 3},
            {'code': 'CFFN004', 'name': '收到其他与筹资活动有关的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 4},
            {'code': 'CFFN005', 'name': '筹资活动现金流入小计', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'is_summary': True, 'sort_order': 5},
            {'code': 'CFFN006', 'name': '偿还债务支付的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 6},
            {'code': 'CFFN007', 'name': '分配股利、利润或偿付利息支付的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 7},
            {'code': 'CFFN008', 'name': '其中：子公司支付给少数股东的股利、利润', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 8},
            {'code': 'CFFN009', 'name': '支付其他与筹资活动有关的现金', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'sort_order': 9},
            {'code': 'CFFN010', 'name': '筹资活动现金流出小计', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'is_summary': True, 'sort_order': 10},
            {'code': 'CFFN011', 'name': '筹资活动产生的现金流量净额', 'category_code': 'CF_FINANCING', 'report_type': ReportType.CF, 'subject_category': 'FN', 'is_summary': True, 'sort_order': 11},
            {'code': 'CFX001', 'name': '汇率变动对现金及现金等价物的影响', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 90},
            {'code': 'CFT001', 'name': '现金及现金等价物净增加额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'is_summary': True, 'sort_order': 91},
            {'code': 'CFT002', 'name': '期初现金及现金等价物余额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'sort_order': 92},
            {'code': 'CFT003', 'name': '期末现金及现金等价物余额', 'category_code': 'CF_OPERATING', 'report_type': ReportType.CF, 'subject_category': 'O', 'is_summary': True, 'sort_order': 93},
        ]

        for data in subjects_data:
            category_code = data.pop('category_code')
            stmt = select(AccountSubject).where(AccountSubject.code == data['code'])
            result = await session.execute(stmt)
            subject = result.scalar_one_or_none()
            
            if not subject:
                # 获取分类ID
                data['category_id'] = category_map[category_code]
                subject = AccountSubject(**data)
                session.add(subject)
                print(f"创建科目: {subject.code} - {subject.name}")

        await session.commit()
        print("初始化科目数据完成！")

if __name__ == "__main__":
    asyncio.run(init_subjects())
