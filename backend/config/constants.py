# -*- coding: utf-8 -*-
# @Time: 2026/1/27 14:07
# @Author : aceplus
# @Desc : ==============================================
# Life is Short I Use Python!!!                      ===
# If this runs wrong,don't ask me,I don't know why.  ===
# If this runs right,thank god,and I don't know why. ===
# Maybe the answer,my friend,is blowing in the wind. ===
# ======================================================
# @Project : ZHANGXJ
# @FileName: constants.py
# @Software: PyCharm


AGENT_CONFIG = {
    "portfolio_manager": {
        "name": "Portfolio Manager",
        "role": "Portfolio Manager",
        "avatar": "pm",
        "is_team_role": True,
    },
    "risk_manager": {
        "name": "Risk Manager",
        "role": "Risk Manager",
        "avatar": "risk",
        "is_team_role": True,
    },
    "fundamentals_analyst": {
        "name": "Fundamentals Analyst",
        "role": "Fundamentals Analyst",
        "avatar": "fundamentals",
        "is_team_role": False,
    },
    "valuation_analyst": {
        "name": "Valuation Analyst",
        "role": "Valuation Analyst",
        "avatar": "valuation",
        "is_team_role": False,
    },
}

ANALYST_TYPES = {
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "agent_id": "fundamentals_analyst",
        "description": "Uses LLM to intelligently select analysis tools, focuses on financial data and company fundamental analysis",
        "order": 11,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "agent_id": "valuation_analyst",
        "description": "Uses LLM to intelligently select analysis tools, focuses on company valuation and value assessment",
        "order": 12,
    },
    # "comprehensive_analyst": {
    #     "display_name": "Comprehensive Analyst",
    #     "agent_id": "comprehensive_analyst",
    #     "description": "Uses LLM to intelligently select analysis tools, performs comprehensive analysis",
    #     "order": 15
    # }
}
