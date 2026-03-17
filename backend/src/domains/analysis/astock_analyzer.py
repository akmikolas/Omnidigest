"""
A股趋势分析服务。基于财经新闻和市场数据进行盘前、盘中、盘后走势预测和分析。
A-share market trend analysis service. Provides pre-market, intraday, and post-market
trend predictions and analysis based on financial news and market data.
"""
import logging
import json
import uuid
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from ...config import settings
from ...core.database import DatabaseManager
from .market_data import MarketDataService, _disable_proxy, _restore_proxy

logger = logging.getLogger(__name__)


class IndexPrediction(BaseModel):
    """
    Prediction result for a single index.
    单个指数的预测结果。
    """
    direction: str = Field(description="上涨/下跌/震荡 / up/down/neutral")
    confidence: int = Field(description="置信度 0-100 / Confidence score 0-100")
    reason: str = Field(description="预测理由 / Prediction reason")


class AStockAnalysisResult(BaseModel):
    """
    A-share market analysis result.
    A股分析结果。
    """
    shanghai: IndexPrediction
    shenzhen: IndexPrediction
    overall_sentiment: str = Field(description="乐观/谨慎/悲观 / optimistic/cautious/pessimistic")
    key_drivers: list[str] = Field(description="主要驱动因素 / Key driving factors")


class MarketContext(BaseModel):
    """
    Market context data.
    市场上下文数据。
    """
    index_type: str
    yesterday_close: Optional[float] = None
    yesterday_change: Optional[float] = None
    today_open: Optional[float] = None
    current_price: Optional[float] = None
    current_change: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    update_time: Optional[str] = None


class AStockAnalyzer:
    """
    A股趋势分析服务。基于财经新闻进行盘前和盘中走势预测。
    A-share market trend analysis service. Provides pre-market and intraday trend predictions
    based on financial news.
    """

    # 财经相关关键词（用于初步筛选）
    # Financial-related keywords for initial filtering.
    MARKET_KEYWORDS = [
        "A股", "股市", "大盘", "指数", "上证", "深证", "创业板", "科创板",
        "宏观经济", "货币政策", "财政政策", "央行", "美联储", "利率", "降息", "加息",
        "GDP", "CPI", "PPI", "PMI", "进出口", "贸易", "外汇", "人民币", "美元",
        "房地产", "房价", "限购", "房贷", "土地", "开发商",
        "新能源", "光伏", "锂电池", "电动车", "汽车",
        "半导体", "芯片", "集成电路", "AI", "人工智能", "大模型",
        "银行", "保险", "券商", "基金", "私募", "公募",
        "IPO", "上市", "退市", "并购", "重组",
        "财报", "业绩", "利润", "营收", "亏损",
        "政策", "监管", "证监会", "银保监会", "工信部", "发改委",
        "国际", "美股", "港股", "欧洲", "亚洲", "全球",
        "大宗商品", "石油", "黄金", "煤炭", "钢铁",
        "消费", "零售", "电商", "餐饮", "旅游",
        "医药", "医疗", "疫苗", "医疗器械",
        "军工", "航天", "航空",
        "基建", "工程", "水泥", "工程机械",
        "环保", "碳中和", "碳达峰", "绿色",
    ]

    def __init__(self, db: DatabaseManager, llm_manager):
        """
        初始化A股分析器

        Args:
            db: 数据库管理器实例
            llm_manager: LLM管理器实例
        """
        self.db = db
        self.llm = llm_manager
        self.market_data = MarketDataService()

    def get_market_context(self, include_realtime: bool = True) -> Dict[str, Dict]:
        """
        获取市场上下文数据

        Args:
            include_realtime: 是否包含实时数据

        Returns:
            市场上下文字典
        """
        context = {}

        for index_type in ["shanghai", "shenzhen"]:
            # 昨日收盘
            yesterday = self.market_data.get_yesterday_close(index_type)
            # 实时行情
            realtime = self.market_data.get_realtime_quote(index_type) if include_realtime else None

            ctx = {
                "yesterday_close": yesterday.get("close") if yesterday else None,
                "yesterday_date": yesterday.get("date") if yesterday else None,
                "today_open": realtime.get("open") if realtime else None,
                "current_price": realtime.get("current_price") if realtime else None,
                "current_change": realtime.get("change") if realtime else None,
                "high": realtime.get("high") if realtime else None,
                "low": realtime.get("low") if realtime else None,
                "volume": realtime.get("volume") if realtime else None,
                "update_time": realtime.get("update_time") if realtime else None,
            }
            context[index_type] = ctx

        return context

    def _get_market_news_from_all_sources(self, hours: int = 24) -> list:
        """
        从三个新闻源获取可能影响A股市场的新闻
        使用简化查询获取近期新闻，让LLM做更精准的过滤

        Args:
            hours: 回溯小时数

        Returns:
            新闻列表
        """
        # news_articles: title, content, source_name, publish_time
        query1 = """
        SELECT id, title, content, source_url, source_name, publish_time, 'news_articles' as source_table
        FROM news_articles
        WHERE publish_time > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - (%s || ' hours')::INTERVAL
        """

        # breaking_stream_raw: raw_text (as content), author (as source_name), publish_time
        query2 = """
        SELECT id, raw_text as content, source_url, author as source_name, publish_time,
               'breaking_stream_raw' as source_table,
               raw_text as title  -- use raw_text as title fallback
        FROM breaking_stream_raw
        WHERE publish_time > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - (%s || ' hours')::INTERVAL
        """

        # twitter_stream_raw: raw_text (as content), author_screen_name, created_at (as publish_time), no source_url
        query3 = """
        SELECT id, raw_text as content, null as source_url, author_screen_name as source_name, created_at as publish_time,
               'twitter_stream_raw' as source_table,
               raw_text as title
        FROM twitter_stream_raw
        WHERE created_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - (%s || ' hours')::INTERVAL
        """

        try:
            with self.db._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Execute each query separately and combine
                    logger.debug(f"Executing query1 with hours={hours}")
                    cur.execute(query1, (str(hours),))
                    news_articles = cur.fetchall()
                    logger.debug(f"query1 returned {len(news_articles)} rows")

                    logger.debug(f"Executing query2 with hours={hours}")
                    cur.execute(query2, (str(hours),))
                    breaking_news = cur.fetchall()
                    logger.debug(f"query2 returned {len(breaking_news)} rows")

                    logger.debug(f"Executing query3 with hours={hours}")
                    cur.execute(query3, (str(hours),))
                    twitter_news = cur.fetchall()
                    logger.debug(f"query3 returned {len(twitter_news)} rows")

                    # Combine and sort by publish_time
                    all_news = news_articles + breaking_news + twitter_news
                    all_news.sort(key=lambda x: x.get('publish_time') or 0, reverse=True)

                    return all_news[:50]  # Limit to 50
        except Exception as e:
            import traceback
            logger.error(f"Error fetching market news: {e}")
            logger.error(traceback.format_exc())
            return []

    def _format_news_for_llm(self, news_list: list) -> str:
        """
        将新闻列表格式化为LLM输入

        Args:
            news_list: 新闻列表

        Returns:
            格式化的新闻文本
        """
        if not news_list:
            return "无相关新闻"

        formatted = []
        for i, news in enumerate(news_list[:20], 1):  # 限制20条
            title = news.get('title', '无标题') or '无标题'
            content = news.get('content', '')[:500] if news.get('content') else ''
            source = news.get('source_name', '未知来源') or '未知来源'
            pub_time = news.get('publish_time')
            time_str = pub_time.strftime("%Y-%m-%d %H:%M") if pub_time else ''

            formatted.append(f"""### 新闻 {i}
标题: {title}
来源: {source} | 时间: {time_str}
内容: {content}
---""")

        return "\n".join(formatted)

    def _format_market_context(self, context: Dict, session: str = "pre_market") -> str:
        """
        将市场上下文格式化为LLM输入

        Args:
            context: 市场上下文字典
            session: 盘前(pre_market)/盘中(intraday)/盘后(post_market)

        Returns:
            格式化的市场文本
        """
        lines = []

        for index_type, data in context.items():
            index_name = "上证指数" if index_type == "shanghai" else "深证成指"

            if session == "pre_market":
                # 昨日收盘
                yesterday = data.get("yesterday_close")
                yesterday_date = data.get("yesterday_date", "N/A")
                lines.append(f"**{index_name}** ({yesterday_date}):")
                lines.append(f"  - 昨日收盘价: {yesterday}")

            elif session == "intraday":
                # 今日走势
                today_open = data.get("today_open")
                current_price = data.get("current_price")
                current_change = data.get("current_change")
                high = data.get("high")
                low = data.get("low")

                lines.append(f"**{index_name}** (今日盘中):")
                if today_open:
                    lines.append(f"  - 开盘: {today_open}")
                if current_price:
                    lines.append(f"  - 当前: {current_price}")
                if current_change is not None:
                    lines.append(f"  - 涨跌幅: {current_change:.2f}%")
                if high:
                    lines.append(f"  - 最高: {high}")
                if low:
                    lines.append(f"  - 最低: {low}")

            elif session == "post_market":
                # 今日收盘
                yesterday = data.get("yesterday_close")
                current_price = data.get("current_price")
                current_change = data.get("current_change")

                lines.append(f"**{index_name}** (今日收盘):")
                if yesterday:
                    lines.append(f"  - 昨日收盘: {yesterday}")
                if current_price:
                    lines.append(f"  - 今日收盘: {current_price}")
                if current_change is not None:
                    lines.append(f"  - 今日涨跌幅: {current_change:.2f}%")

        return "\n".join(lines) if lines else "暂无市场数据"

    async def pre_market_analysis(self, index_type: str = "both") -> Optional[dict]:
        """
        盘前分析：在开盘前分析过去24小时的财经新闻，结合昨日收盘数据

        Args:
            index_type: 'shanghai', 'shenzhen', 或 'both'

        Returns:
            分析结果字典
        """
        logger.info(f"Starting pre-market A-stock analysis for {index_type}...")

        # 1. 获取市场上下文（昨日收盘数据）
        market_context = self.get_market_context(include_realtime=False)
        logger.info(f"Market context: {market_context}")

        # 2. 获取过去24小时的财经类新闻
        news_list = self._get_market_news_from_all_sources(hours=settings.astock_news_hours)

        if not news_list:
            logger.warning("No market-related news found for pre-market analysis")
            return None

        logger.info(f"Found {len(news_list)} market-related news articles")

        # 3. 格式化新闻上下文
        news_context = self._format_news_for_llm(news_list)

        # 4. 格式化市场上下文
        market_ctx_str = self._format_market_context(market_context, "pre_market")

        system_prompt = """你是一位资深A股分析师。你的任务是结合市场昨日走势和财经新闻，预测今日大盘走势。

### 输出格式要求（JSON）：
{
    "shanghai": {"direction": "上涨/下跌/震荡", "confidence": 0-100, "reason": "简要理由"},
    "shenzhen": {"direction": "上涨/下跌/震荡", "confidence": 0-100, "reason": "简要理由"},
    "overall_sentiment": "乐观/谨慎/悲观",
    "key_drivers": ["驱动因素1", "驱动因素2"]
}

注意：
1. direction 只允许：上涨、下跌、震荡
2. confidence 为 0-100 的整数
3. reason 简要说明预测理由，结合市场和新闻分析
4. overall_sentiment 为总体情绪
5. key_drivers 列出2-4个主要驱动因素"""

        user_prompt = f"""### 昨日市场走势（参考）：

{market_ctx_str}

### 财经新闻（过去24小时）：

{news_context}

请基于以上昨日走势和市场新闻，分析对上证指数和深证指数的影响，给出今日走势预测。"""

        _disable_proxy()  # 临时禁用代理
        try:
            result = await self.llm.chat_completion_structured(
                response_model=AStockAnalysisResult,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                service_name="astock_pre_market"
            )

            # 3. 记录预测到数据库
            prediction_date = datetime.now().date()

            # 记录上证预测
            shanghai_id = await self.record_prediction(
                index_type="shanghai",
                prediction_type="pre_market",
                direction=result.shanghai.direction,
                confidence=result.shanghai.confidence,
                news_summary=result.shanghai.reason
            )

            # 记录深证预测
            shenzhen_id = await self.record_prediction(
                index_type="shenzhen",
                prediction_type="pre_market",
                direction=result.shenzhen.direction,
                confidence=result.shenzhen.confidence,
                news_summary=result.shenzhen.reason
            )

            return {
                "prediction_date": prediction_date.isoformat(),
                "prediction_type": "pre_market",
                "shanghai": {
                    "direction": result.shanghai.direction,
                    "confidence": result.shanghai.confidence,
                    "reason": result.shanghai.reason,
                    "prediction_id": str(shanghai_id) if shanghai_id else None
                },
                "shenzhen": {
                    "direction": result.shenzhen.direction,
                    "confidence": result.shenzhen.confidence,
                    "reason": result.shenzhen.reason,
                    "prediction_id": str(shenzhen_id) if shenzhen_id else None
                },
                "overall_sentiment": result.overall_sentiment,
                "key_drivers": result.key_drivers,
                "news_count": len(news_list)
            }

        except Exception as e:
            logger.error(f"Error in pre-market analysis: {e}")
            return None
        finally:
            _restore_proxy()  # 恢复代理设置

    async def intraday_analysis(self, index_type: str = "both") -> Optional[dict]:
        """
        盘中分析：基于当日财经新闻和上午走势更新走势预测

        Args:
            index_type: 'shanghai', 'shenzhen', 或 'both'

        Returns:
            分析结果字典
        """
        logger.info(f"Starting intraday A-stock analysis for {index_type}...")

        # 1. 获取市场实时数据
        market_context = self.get_market_context(include_realtime=True)
        logger.info(f"Intraday market context: {market_context}")

        # 2. 获取当日财经新闻
        news_list = self._get_market_news_from_all_sources(hours=12)

        if not news_list:
            logger.warning("No market-related news found for intraday analysis")
            return None

        logger.info(f"Found {len(news_list)} market-related news articles for intraday")

        # 3. 格式化上下文
        news_context = self._format_news_for_llm(news_list)
        market_ctx_str = self._format_market_context(market_context, "intraday")

        system_prompt = """你是一位资深A股分析师。你的任务是结合今日盘中走势和财经新闻，更新对大盘走势的判断。

### 输出格式要求（JSON）：
{
    "shanghai": {"direction": "上涨/下跌/震荡", "confidence": 0-100, "reason": "简要理由"},
    "shenzhen": {"direction": "上涨/下跌/震荡", "confidence": 0-100, "reason": "简要理由"},
    "overall_sentiment": "乐观/谨慎/悲观",
    "key_drivers": ["驱动因素1", "驱动因素2"]
}

注意：
1. direction 只允许：上涨、下跌、震荡
2. confidence 为 0-100 的整数
3. reason 简要说明预测理由，结合盘中走势和新闻
4. overall_sentiment 为总体情绪
5. key_drivers 列出2-4个主要驱动因素"""

        user_prompt = f"""### 今日盘中走势：

{market_ctx_str}

### 当日盘中财经新闻：

{news_context}

请基于以上盘中走势和新闻，分析对上证指数和深证指数的影响，给出走势判断。"""

        _disable_proxy()  # 临时禁用代理
        try:
            result = await self.llm.chat_completion_structured(
                response_model=AStockAnalysisResult,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                service_name="astock_intraday"
            )

            # 记录盘中预测
            prediction_date = datetime.now().date()

            shanghai_id = await self.record_prediction(
                index_type="shanghai",
                prediction_type="intraday",
                direction=result.shanghai.direction,
                confidence=result.shanghai.confidence,
                news_summary=result.shanghai.reason
            )

            shenzhen_id = await self.record_prediction(
                index_type="shenzhen",
                prediction_type="intraday",
                direction=result.shenzhen.direction,
                confidence=result.shenzhen.confidence,
                news_summary=result.shenzhen.reason
            )

            return {
                "prediction_date": prediction_date.isoformat(),
                "prediction_type": "intraday",
                "shanghai": {
                    "direction": result.shanghai.direction,
                    "confidence": result.shanghai.confidence,
                    "reason": result.shanghai.reason,
                    "prediction_id": str(shanghai_id) if shanghai_id else None
                },
                "shenzhen": {
                    "direction": result.shenzhen.direction,
                    "confidence": result.shenzhen.confidence,
                    "reason": result.shenzhen.reason,
                    "prediction_id": str(shenzhen_id) if shenzhen_id else None
                },
                "overall_sentiment": result.overall_sentiment,
                "key_drivers": result.key_drivers,
                "news_count": len(news_list)
            }

        except Exception as e:
            logger.error(f"Error in intraday analysis: {e}")
            return None
        finally:
            _restore_proxy()  # 恢复代理设置

    async def record_prediction(
        self,
        index_type: str,
        prediction_type: str,
        direction: str,
        confidence: int,
        news_summary: str
    ) -> Optional[str]:
        """
        记录预测结果到数据库

        Args:
            index_type: 'shanghai' 或 'shenzhen'
            prediction_type: 'pre_market' 或 'intraday'
            direction: 预测方向
            confidence: 置信度
            news_summary: 新闻摘要

        Returns:
            预测记录ID
        """
        query = """
        INSERT INTO astock_predictions (
            id, prediction_date, index_type, prediction_type,
            prediction_direction, confidence_score, news_summary, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """

        try:
            prediction_id = str(uuid.uuid4())
            now = datetime.now()
            prediction_date = now.date()

            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (
                        prediction_id,
                        prediction_date,
                        index_type,
                        prediction_type,
                        direction,
                        confidence,
                        news_summary,
                        now,
                        now
                    ))
                    result = cur.fetchone()
                conn.commit()

            logger.info(f"Recorded {index_type} {prediction_type} prediction: {direction} (confidence: {confidence})")
            return result[0] if result else None

        except Exception as e:
            logger.error(f"Error recording prediction: {e}")
            return None

    async def post_market_analysis(self, index_type: str = "both") -> Optional[dict]:
        """
        盘后分析：对比预测与实际走势，分析差异原因，并更新准确率

        Args:
            index_type: 'shanghai', 'shenzhen', 或 'both'

        Returns:
            分析结果字典，包含预测对比和差异分析
        """
        logger.info(f"Starting post-market A-stock analysis for {index_type}...")

        # 1. 获取今日收盘数据
        market_context = self.get_market_context(include_realtime=True)
        logger.info(f"Post-market context: {market_context}")

        # 2. 获取今日的预测记录
        today = datetime.now().date()
        predictions = self._get_today_predictions(today)

        if not predictions:
            logger.warning(f"No predictions found for today {today}")
            return None

        # 3. 获取今日财经新闻（用于分析差异）
        news_list = self._get_market_news_from_all_sources(hours=24)
        news_context = self._format_news_for_llm(news_list) if news_list else "无相关新闻"

        # 4. 格式化市场数据
        market_ctx_str = self._format_market_context(market_context, "post_market")

        # 5. 构建对比分析
        comparison = {}
        for pred in predictions:
            idx = pred['index_type']
            pred_direction = pred['prediction_direction']
            pred_type = pred['prediction_type']

            # 获取实际涨跌幅
            actual_change = market_context.get(idx, {}).get("current_change")

            if actual_change is not None:
                # 计算是否正确
                if pred_direction == "上涨" and actual_change > 0:
                    is_correct = True
                elif pred_direction == "下跌" and actual_change < 0:
                    is_correct = True
                elif pred_direction == "震荡":
                    is_correct = True
                else:
                    is_correct = False

                comparison[idx] = {
                    "prediction_type": pred_type,
                    "predicted_direction": pred_direction,
                    "confidence": pred['confidence_score'],
                    "actual_change": round(actual_change, 2),
                    "is_correct": is_correct,
                }

                # 更新数据库
                await self.update_actual_result(str(pred['id']), actual_change)

        # 6. 使用LLM分析预测与实际的差异
        system_prompt = """你是一位资深A股分析师。你的任务是分析今日A股预测与实际走势的差异，并给出原因分析。

### 输出格式要求（JSON）：
{
    "analysis": "差异原因分析（2-3句话）",
    "key_factors": ["差异因素1", "差异因素2", "差异因素3"]
}

注意：
1. 分析预测与实际走势差异的原因
2. 考虑新闻面、技术面、资金面等因素
3. 提出后续关注的要点"""

        user_prompt = f"""### 今日市场走势（实际）：

{market_ctx_str}

### 今日预测vs实际：

{json.dumps(comparison, ensure_ascii=False, indent=2)}

### 今日财经新闻（参考）：

{news_context}

请分析预测与实际走势的差异原因。"""

        _disable_proxy()  # 临时禁用代理，避免 LLM 调用时代理问题
        try:
            class DiffAnalysis(BaseModel):
                """
                Data model for prediction vs actual difference analysis.
                预测与实际走势差异分析的数据模型。
                """
                analysis: str = Field(description="差异原因分析")
                key_factors: list[str] = Field(description="关键因素列表")

            result = await self.llm.chat_completion_structured(
                response_model=DiffAnalysis,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                service_name="astock_post_market"
            )

            # 统计准确率
            correct_count = sum(1 for c in comparison.values() if c.get("is_correct"))
            total_count = len(comparison)
            accuracy = (correct_count / total_count * 100) if total_count > 0 else 0

            return {
                "prediction_date": today.isoformat(),
                "prediction_type": "post_market",
                "comparison": comparison,
                "analysis": result.analysis if result else "分析失败",
                "key_factors": result.key_factors if result else [],
                "accuracy": round(accuracy, 1),
                "correct_count": correct_count,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(f"Error in post-market analysis: {e}")
            # 即使LLM分析失败，也返回基础对比数据
            return {
                "prediction_date": today.isoformat(),
                "prediction_type": "post_market",
                "comparison": comparison,
                "error": str(e)
            }
        finally:
            _restore_proxy()  # 恢复代理设置

    def _get_today_predictions(self, date) -> list:
        """获取指定日期的预测记录"""
        query = """
        SELECT id, index_type, prediction_type, prediction_direction, confidence_score
        FROM astock_predictions
        WHERE prediction_date = %s
        ORDER BY index_type, prediction_type
        """
        try:
            with self.db._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (date,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching predictions: {e}")
            return []

    async def update_actual_result(self, prediction_id: str, actual_change: float) -> bool:
        """
        收盘后更新实际结果并计算准确率

        Args:
            prediction_id: 预测记录ID
            actual_change: 实际涨跌幅（百分比，如 1.5 表示上涨1.5%）

        Returns:
            是否更新成功
        """
        # 先获取预测的方向
        query_select = "SELECT prediction_direction FROM astock_predictions WHERE id = %s"

        # 更新实际结果
        query_update = """
        UPDATE astock_predictions
        SET actual_close_change = %s,
            is_correct = CASE
                WHEN prediction_direction = '上涨' AND %s > 0 THEN TRUE
                WHEN prediction_direction = '下跌' AND %s < 0 THEN TRUE
                WHEN prediction_direction = '震荡' THEN TRUE
                ELSE FALSE
            END,
            updated_at = %s
        WHERE id = %s
        """

        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_update, (
                        actual_change,
                        actual_change,
                        actual_change,
                        datetime.now(),
                        prediction_id
                    ))
                conn.commit()

            logger.info(f"Updated actual result for prediction {prediction_id}: {actual_change}%")
            return True

        except Exception as e:
            logger.error(f"Error updating actual result: {e}")
            return False

    async def get_accuracy_stats(self, days: int = 30) -> dict:
        """
        获取历史准确率统计

        Args:
            days: 统计天数

        Returns:
            准确率统计字典
        """
        query = """
        SELECT
            index_type,
            prediction_type,
            COUNT(*) as total_predictions,
            SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) as correct_predictions,
            AVG(confidence_score) as avg_confidence
        FROM astock_predictions
        WHERE prediction_date > CURRENT_DATE - (%s || ' days')::INTERVAL
          AND is_correct IS NOT NULL
        GROUP BY index_type, prediction_type
        """

        try:
            with self.db._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str(days),))
                    results = cur.fetchall()

            stats = []
            for row in results:
                total = row['total_predictions']
                correct = row['correct_predictions']
                accuracy = (correct / total * 100) if total > 0 else 0

                stats.append({
                    "index_type": row['index_type'],
                    "prediction_type": row['prediction_type'],
                    "total_predictions": total,
                    "correct_predictions": correct,
                    "accuracy": round(accuracy, 1),
                    "avg_confidence": round(row['avg_confidence'], 1) if row['avg_confidence'] else 0
                })

            return {
                "period_days": days,
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Error getting accuracy stats: {e}")
            return {"period_days": days, "stats": []}
