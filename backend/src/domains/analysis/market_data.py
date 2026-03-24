"""
A股市场数据服务。使用 AKShare 获取实时指数和历史数据。
A-share market data service. Uses AKShare to fetch real-time index and historical data.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# Proxy environment variables to disable (AKShare needs direct connection to domestic sites).
# 禁用代理的环境变量（AKShare 需要直连国内网站）。
_original_proxy = {}
_PROXY_VARS = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
               'all_proxy', 'ALL_PROXY']


def _disable_proxy():
    """
    Temporarily disable proxy to allow AKShare direct connection.
    临时禁用代理，让 AKShare 直连。
    """
    global _original_proxy
    for var in _PROXY_VARS:
        if var in os.environ:
            _original_proxy[var] = os.environ.pop(var)


def _restore_proxy():
    """
    Restore proxy settings.
    恢复代理设置。
    """
    global _original_proxy
    for var, value in _original_proxy.items():
        os.environ[var] = value
    _original_proxy = {}


class MarketDataService:
    """
    A股市场数据服务。获取实时指数和历史数据。
    """

    # 指数代码映射（Sina 格式: sh000001, sz399001）
    INDEX_CODES = {
        "shanghai": {"name": "上证指数", "symbol": "sh000001"},
        "shenzhen": {"name": "深证成指", "symbol": "sz399001"},
    }

    def __init__(self):
        """初始化市场数据服务"""
        pass

    def get_realtime_quote(self, index_type: str = "shanghai") -> Optional[Dict]:
        """
        获取实时行情（单只股票/指数）

        Args:
            index_type: 指数类型 (shanghai/shenzhen)

        Returns:
            包含指数数据的字典，如果失败返回None
        """
        _disable_proxy()  # 临时禁用代理
        try:
            index_info = self.INDEX_CODES.get(index_type)
            if not index_info:
                logger.warning(f"Unknown index type: {index_type}")
                return None

            symbol = index_info["symbol"]

            # 使用 Sina 数据源获取指数实时行情
            # Sina 不需要代理，可能更容易访问
            df = ak.stock_zh_index_spot_sina()
            if df is None or df.empty:
                logger.warning("Failed to fetch index spot data from Sina")
                return None

            # 筛选对应指数 - Sina 使用纯数字代码
            code_col = '代码' if '代码' in df.columns else 'symbol'
            row = df[df[code_col] == symbol]

            if row.empty:
                logger.warning(f"No data found for {symbol}")
                return None

            data = row.iloc[0]

            # 安全获取数据
            def safe_float(val, default=0):
                """
                Safely convert value to float, returning default if conversion fails.
                安全地将值转换为浮点数，如果转换失败则返回默认值。
                """
                try:
                    return float(val) if pd.notna(val) else default
                except Exception as e:
                    logger.warning(f"Failed to convert value to float: {e}")
                    return default

            result = {
                "index_type": index_type,
                "name": index_info["name"],
                "symbol": symbol,
                "current_price": safe_float(data.get('最新价')),
                "change": safe_float(data.get('涨跌幅')),
                "change_amount": safe_float(data.get('涨跌额')),
                "volume": safe_float(data.get('成交量')),
                "amount": safe_float(data.get('成交额')),
                "high": safe_float(data.get('最高')),
                "low": safe_float(data.get('最低')),
                "open": safe_float(data.get('今开')),
                "prev_close": safe_float(data.get('昨收')),
                "update_time": str(datetime.now()),
            }
            return result

        except Exception as e:
            logger.error(f"Error fetching realtime quote for {index_type}: {e}")
            return None
        finally:
            _restore_proxy()  # 恢复代理

    def get_all_quotes(self) -> Dict[str, Dict]:
        """
        获取所有指数的实时行情

        Returns:
            指数行情字典
        """
        results = {}
        for index_type in self.INDEX_CODES.keys():
            data = self.get_realtime_quote(index_type)
            if data:
                results[index_type] = data
        return results

    def get_yesterday_close(self, index_type: str = "shanghai") -> Optional[Dict]:
        """
        获取昨日收盘价。优先使用实时数据中的昨收价。

        Args:
            index_type: 指数类型

        Returns:
            昨日收盘数据
        """
        try:
            index_info = self.INDEX_CODES.get(index_type)
            if not index_info:
                return None

            # 尝试从实时数据获取昨收价
            realtime = self.get_realtime_quote(index_type)
            if realtime and realtime.get("prev_close"):
                return {
                    "index_type": index_type,
                    "name": index_info["name"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "close": realtime.get("prev_close"),
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching yesterday close for {index_type}: {e}")
            return None

    def get_today_intraday(self, index_type: str = "shanghai") -> Optional[Dict]:
        """
        获取今日盘中数据（当日走势）

        Args:
            index_type: 指数类型

        Returns:
            今日走势数据
        """
        try:
            # 获取实时行情
            realtime = self.get_realtime_quote(index_type)
            if not realtime:
                return None

            index_info = self.INDEX_CODES.get(index_type)

            # 计算上午vs下午的差异（如果有的话）
            # 这里我们简单返回实时数据，因为 AKShare 的分时数据需要额外处理

            result = {
                "index_type": index_type,
                "name": index_info["name"],
                "open": realtime.get("open"),
                "current": realtime.get("current_price"),
                "high": realtime.get("high"),
                "low": realtime.get("low"),
                "change": realtime.get("change"),
                "change_amount": realtime.get("change_amount"),
                "volume": realtime.get("volume"),
                "amount": realtime.get("amount"),
                "amplitude": realtime.get("amplitude"),
                "update_time": realtime.get("update_time"),
            }

            # 如果午间休市（11:30-13:00），可以标记为上午收盘
            now = datetime.now()
            current_time = now.time()

            # 上午盘结束
            if datetime.strptime("11:30", "%H:%M").time() <= current_time <= datetime.strptime("12:00", "%H:%M").time():
                result["session"] = "morning_close"
                result["morning_change"] = None  # 可后续计算
            # 下午盘进行中
            elif current_time > datetime.strptime("13:00", "%H:%M").time():
                result["session"] = "afternoon"

            return result

        except Exception as e:
            logger.error(f"Error fetching intraday data for {index_type}: {e}")
            return None

    def is_market_open(self) -> bool:
        """
        检查当前A股市场是否开盘

        Returns:
            是否开盘
        """
        try:
            now = datetime.now()

            # 周末不开盘
            if now.weekday() >= 5:
                return False

            # A股交易时间: 9:30-11:30, 13:00-15:00
            current_time = now.time()
            morning_start = datetime.strptime("09:30", "%H:%M").time()
            morning_end = datetime.strptime("11:30", "%H:%M").time()
            afternoon_start = datetime.strptime("13:00", "%H:%M").time()
            afternoon_end = datetime.strptime("15:00", "%H:%M").time()

            if morning_start <= current_time <= morning_end:
                return True
            if afternoon_start <= current_time <= afternoon_end:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False

    def get_market_session(self) -> str:
        """
        获取当前市场状态

        Returns:
            pre_market (盘前), morning (上午), lunch (午间), afternoon (下午), closed (收盘), holiday (休市)
        """
        try:
            now = datetime.now()

            # 周末
            if now.weekday() >= 5:
                return "holiday"

            current_time = now.time()

            # 盘前: 9:00-9:30
            if datetime.strptime("09:00", "%H:%M").time() <= current_time < datetime.strptime("09:30", "%H:%M").time():
                return "pre_market"

            # 上午: 9:30-11:30
            if datetime.strptime("09:30", "%H:%M").time() <= current_time <= datetime.strptime("11:30", "%H:%M").time():
                return "morning"

            # 午间: 11:30-13:00
            if datetime.strptime("11:30", "%H:%M").time() < current_time < datetime.strptime("13:00", "%H:%M").time():
                return "lunch"

            # 下午: 13:00-15:00
            if datetime.strptime("13:00", "%H:%M").time() <= current_time <= datetime.strptime("15:00", "%H:%M").time():
                return "afternoon"

            # 收盘后: 15:00-16:00
            if datetime.strptime("15:00", "%H:%M").time() < current_time < datetime.strptime("16:00", "%H:%M").time():
                return "after_close"

            return "closed"

        except Exception as e:
            logger.error(f"Error getting market session: {e}")
            return "unknown"

    def get_index_history(self, symbol: str, period: str = "1m") -> dict:
        """
        获取指数历史K线数据

        Args:
            symbol: 指数代码 (sh000001 沪指, sz399001 深证成指)
            period: 时间范围 1d/1w/1m/3m，1d返回分钟级数据

        Returns:
            {"dates": [...], "prices": [...], "volume": [...]}
        """
        _disable_proxy()
        try:
            # 1d 返回分钟级当日数据
            if period == "1d":
                return self.get_index_intraday(symbol)

            # 其他周期返回日线数据
            period_days = {
                "1w": 30,
                "1m": 90,
                "3m": 180,
            }
            days = period_days.get(period, 90)

            # 使用 stock_zh_index_daily 获取指数数据
            # symbol 格式: sh000001 (上证), sz399001 (深证)
            df = ak.stock_zh_index_daily(symbol=symbol)

            if df is None or df.empty:
                logger.warning(f"No historical data for {symbol}")
                return {"dates": [], "prices": [], "volume": []}

            # 转换日期格式并过滤
            df['date'] = pd.to_datetime(df['date'])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            df = df[df['date'] >= start_date]

            # 返回数据
            return {
                "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
                "prices": df["close"].tolist(),
                "volume": df["volume"].tolist() if "volume" in df.columns else [],
            }

        except Exception as e:
            logger.error(f"Error fetching index history for {symbol}: {e}")
            return {"dates": [], "prices": [], "volume": []}
        finally:
            _restore_proxy()

    def get_index_intraday(self, symbol: str) -> dict:
        """
        获取指数当日分钟级数据

        Args:
            symbol: 指数代码 (sh000001 沪指, sz399001 深证成指)

        Returns:
            {"dates": [...], "prices": [...], "volume": [...]}
        """
        _disable_proxy()
        try:
            # 使用 stock_zh_a_minute 获取分钟级数据
            # period='5' 表示5分钟K线
            df = ak.stock_zh_a_minute(symbol=symbol, period='5', adjust='')

            if df is None or df.empty:
                logger.warning(f"No intraday data for {symbol}")
                return {"dates": [], "prices": [], "volume": []}

            # 返回分钟级数据
            return {
                "dates": df["day"].tolist(),
                "prices": df["close"].tolist(),
                "volume": df["volume"].tolist(),
            }

        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return {"dates": [], "prices": [], "volume": []}
        finally:
            _restore_proxy()
