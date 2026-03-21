"""
A股异常波动检测与推送服务
A-share abnormal fluctuation detection and notification service
"""
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from ..config import settings
from ..core.database import DatabaseManager
from ..domains.analysis.market_data import MarketDataService
from ..notifications.pusher import NotificationService

logger = logging.getLogger(__name__)


class AStockAlertService:
    """
    A股异常波动检测服务
    检测指数和个股的异常波动，并推送通知
    """

    # 需要监控的指数
    WATCHED_INDICES = {
        "sh000001": {"name": "上证指数", "type": "index"},
        "sz399001": {"name": "深证成指", "type": "index"},
    }

    # 需要监控的热门个股
    WATCHED_STOCKS = {
        "sh600519": {"name": "贵州茅台", "type": "stock"},
        "sz000858": {"name": "五粮液", "type": "stock"},
        "sh600036": {"name": "招商银行", "type": "stock"},
        "sh601318": {"name": "中国平安", "type": "stock"},
        "sh600276": {"name": "恒瑞医药", "type": "stock"},
        "sz002594": {"name": "比亚迪", "type": "stock"},
        "sz300750": {"name": "宁德时代", "type": "stock"},
    }

    def __init__(self):
        self.market_data = MarketDataService()
        self.db = DatabaseManager()
        self.pusher = NotificationService()
        self._last_alert_time = {}  # 上次告警时间，避免重复告警

    def check_price_fluctuation(self, current_change: float) -> bool:
        """
        检查价格涨跌幅是否异常

        Args:
            current_change: 当前涨跌幅 (%)

        Returns:
            是否异常
        """
        threshold = getattr(settings, 'astock_alert_threshold', 3.0)
        return abs(current_change) >= threshold

    def check_volume_fluctuation(self, current_volume: float, avg_volume: float) -> bool:
        """
        检查成交量是否异常

        Args:
            current_volume: 当前成交量
            avg_volume: 平均成交量

        Returns:
            是否异常
        """
        if avg_volume <= 0:
            return False
        multiplier = getattr(settings, 'astock_alert_volume_multiplier', 2.0)
        return current_volume >= avg_volume * multiplier

    def _should_alert(self, symbol: str) -> bool:
        """
        检查是否应该发送告警（避免频繁告警）

        Args:
            symbol: 股票代码

        Returns:
            是否应该告警
        """
        import time
        now = time.time()
        last_time = self._last_alert_time.get(symbol, 0)
        # 同一个标的至少间隔 30 分钟告警一次
        return (now - last_time) > 1800

    def _record_alert(self, symbol: str):
        """记录告警时间"""
        import time
        self._last_alert_time[symbol] = time.time()

    async def check_indices(self) -> List[Dict]:
        """
        检查指数异常波动

        Returns:
            异常列表
        """
        anomalies = []

        for symbol, info in self.WATCHED_INDICES.items():
            try:
                # 获取实时行情
                if symbol == "sh000001":
                    data = self.market_data.get_realtime_quote("shanghai")
                else:
                    data = self.market_data.get_realtime_quote("shenzhen")

                if not data:
                    continue

                change = data.get("change", 0)
                volume = data.get("volume", 0)

                # 检查涨跌幅异常
                if self.check_price_fluctuation(change) and self._should_alert(symbol):
                    anomalies.append({
                        "symbol": symbol,
                        "name": info["name"],
                        "type": "index",
                        "alert_type": "price",
                        "current_price": data.get("current_price"),
                        "change": change,
                        "volume": volume,
                        "message": f"【{info['name']}】涨跌幅异常: {change:+.2f}%"
                    })
                    self._record_alert(symbol)

            except Exception as e:
                logger.error(f"Error checking index {symbol}: {e}")

        return anomalies

    async def check_stocks(self) -> List[Dict]:
        """
        检查个股异常波动

        Returns:
            异常列表
        """
        import akshare as ak
        import pandas as pd
        from ..domains.analysis.market_data import _disable_proxy, _restore_proxy

        anomalies = []

        _disable_proxy()
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                logger.warning("Failed to fetch stock data")
                return anomalies

            for symbol, info in self.WATCHED_STOCKS.items():
                try:
                    code = symbol[2:]  # 去掉 sh/sz 前缀
                    row = df[df['代码'] == code] if '代码' in df.columns else None

                    if row is None or row.empty:
                        continue

                    data = row.iloc[0]
                    change = float(data.get('涨跌幅', 0)) if pd.notna(data.get('涨跌幅')) else 0
                    volume = float(data.get('成交量', 0)) if pd.notna(data.get('成交量')) else 0

                    # 检查涨跌幅异常
                    if self.check_price_fluctuation(change) and self._should_alert(symbol):
                        anomalies.append({
                            "symbol": symbol,
                            "name": info["name"],
                            "type": "stock",
                            "alert_type": "price",
                            "current_price": data.get('最新价'),
                            "change": change,
                            "volume": volume,
                            "message": f"【{info['name']}】({symbol}) 涨跌幅异常: {change:+.2f}%"
                        })
                        self._record_alert(symbol)

                except Exception as e:
                    logger.error(f"Error checking stock {symbol}: {e}")

        except Exception as e:
            logger.error(f"Error fetching stock market data: {e}")
        finally:
            _restore_proxy()

        return anomalies

    async def send_alert_notification(self, anomalies: List[Dict]):
        """
        发送异常波动通知

        Args:
            anomalies: 异常列表
        """
        if not anomalies:
            return

        # 构建通知内容
        title = f"A股异常波动告警 ({len(anomalies)}条)"

        # 按类型分组
        index_alerts = [a for a in anomalies if a["type"] == "index"]
        stock_alerts = [a for a in anomalies if a["type"] == "stock"]

        summary = f"发现 {len(anomalies)} 项异常波动:\n\n"
        if index_alerts:
            summary += "【指数异常】\n"
            for a in index_alerts:
                summary += f"• {a['message']}\n"
            summary += "\n"

        if stock_alerts:
            summary += "【个股异常】\n"
            for a in stock_alerts:
                summary += f"• {a['message']}\n"

        # 发送到钉钉
        if getattr(settings, 'astock_alert_push_dingtalk', True):
            await self._send_dingtalk(title, summary, anomalies)

        # 发送到 Telegram
        if getattr(settings, 'astock_alert_push_telegram', True):
            await self._send_telegram(title, summary, anomalies)

    async def _send_dingtalk(self, title: str, summary: str, anomalies: List[Dict]):
        """发送到钉钉"""
        try:
            from ..notifications import NotificationManager
            manager = NotificationManager()
            # Send to all DingTalk channels
            await manager.send_message(
                summary,
                channels=["dingtalk"],
                title=title
            )
            logger.info(f"Sent DingTalk alert for {len(anomalies)} anomalies")

        except Exception as e:
            logger.error(f"Error sending DingTalk alert: {e}")

    async def _send_telegram(self, title: str, summary: str, anomalies: List[Dict]):
        """发送到 Telegram"""
        try:
            from ..notifications import NotificationManager
            manager = NotificationManager()
            # Send to all Telegram channels
            await manager.send_message(
                f"*{title}*\n\n{summary}",
                channels=["telegram"]
            )
            logger.info(f"Sent Telegram alert for {len(anomalies)} anomalies")

        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")

    async def run_check(self) -> Dict:
        """
        执行一次异常检测

        Returns:
            检测结果
        """
        logger.info("Starting A-stock abnormal fluctuation check...")

        # 检查是否启用
        if not getattr(settings, 'enable_astock_alert', True):
            return {"status": "disabled", "message": "A-stock alert is disabled"}

        # 检查市场是否开盘
        if not self.market_data.is_market_open():
            return {"status": "skipped", "message": "Market is closed"}

        # 检查指数
        index_anomalies = await self.check_indices()

        # 检查个股
        stock_anomalies = await self.check_stocks()

        # 合并结果
        all_anomalies = index_anomalies + stock_anomalies

        # 发送通知
        if all_anomalies:
            await self.send_alert_notification(all_anomalies)

        result = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "index_anomalies": len(index_anomalies),
            "stock_anomalies": len(stock_anomalies),
            "total_anomalies": len(all_anomalies),
            "anomalies": all_anomalies
        }

        logger.info(f"A-stock check completed: {len(all_anomalies)} anomalies found")
        return result


# 全局实例
_alert_service = None


def get_alert_service() -> AStockAlertService:
    """获取告警服务单例"""
    global _alert_service
    if _alert_service is None:
        _alert_service = AStockAlertService()
    return _alert_service
