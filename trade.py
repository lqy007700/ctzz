import json
import logging
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from binance.error import ClientError
from binance.um_futures import UMFutures
from ding_talk import DingTalk
import pandas as pd
import numpy as np


class Trade:
    client = None

    d = None

    symbolsInfoMap = {}

    interval = '5m'  # k 线间隔

    # 持仓记录
    positions = {}

    ### 配置信息
    symbols = []

    # 最大持仓
    maxPositionCount = 0

    # 每单保证金
    costPerOrder = 0
    key = ""
    secret = ""

    def __init__(self):
        self.d = DingTalk()
        self.init_log()

        self.init_config()
        if not self.symbols or self.maxPositionCount == 0 or self.costPerOrder == 0:
            self.d.error("配置错误启动失败")
            exit(-1)

        self.client = UMFutures(key=self.key, secret=self.secret)
        self.get_symbol_list()
        self.d.normal("启动")

    # 获取 k 线数据
    def get_klines(self, symbol, interval, limit=104):
        klines = self.client.klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                           'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                                           'taker_buy_quote_asset_volume', 'ignore'])
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    def calculate_macd(self, df, fast_period=12, slow_period=26, signal_period=9):
        df['ema_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['signal'] = df['macd'].ewm(span=signal_period, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal']
        return df

    # 判断金叉和死叉
    def detect_crosses(self, df):
        df['prev_macd'] = df['macd'].shift(1)
        df['prev_signal'] = df['signal'].shift(1)
        df['golden_cross'] = (df['macd'] > df['signal']) & (df['prev_macd'] <= df['prev_signal'])
        df['death_cross'] = (df['macd'] < df['signal']) & (df['prev_macd'] >= df['prev_signal'])
        return df

    # 获取币对信息
    def get_symbol_list(self):
        res = self.client.exchange_info()
        if 'symbols' in res:
            for info in res['symbols']:
                tmp = info['symbol']
                if 'USDT' in tmp:
                    if '_' in tmp:
                        continue
                    self.symbolsInfoMap[tmp] = info

    # 执行交易操作
    def place_order(self, symbol, side, price):
        try:
            if symbol not in self.symbolsInfoMap:
                logging.info(f"币对不存在{symbol}")
                return

            # 数量小数精度
            quantityPrecision = self.symbolsInfoMap[symbol]['quantityPrecision']
            quantity = round(self.costPerOrder / float(price), quantityPrecision)

            positionSide = {
                'SELL': 'SHORT',
                'BUY': 'LONG'
            }
            params = {
                'symbol': symbol,
                'side': side,  # SELL, BUY
                'positionSide': positionSide.get(side),  # LONG, SHORT
                'type': 'MARKET',
                'quantity': quantity,
            }
            logging.info(f"下单: {json.dumps(params)}")
            order = self.client.new_order(**params)
            logging.info(f"下单结果:{json.dumps(order)}")
            self.d.order(params, price)
            self.positions[symbol] = {'side': side, 'entry_price': price, 'check_open_price': False}
            return order
        except ClientError as error:
            msg = "下单失败 status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
            self.d.error(msg)
            logging.error(msg)
            return None

    # 平仓
    def stop_price_order(self, symbol, side, price, profit):
        try:
            if symbol not in self.symbolsInfoMap:
                logging.error(f"币对不存在{symbol}")
                return

            # 数量最大
            maxQty = self.symbolsInfoMap[symbol]['filters'][1]['maxQty']
            positionSide = {
                'SELL': 'LONG',
                'BUY': 'SHORT'
            }

            params = {
                'symbol': symbol,
                'side': side,  # SELL, BUY
                'positionSide': positionSide.get(side),  # LONG, SHORT
                'type': 'MARKET',
                'quantity': maxQty,  # 全部平仓
            }
            logging.info(f"是否止盈{profit}；平仓: {json.dumps(params)}")
            order = self.client.new_order(**params)
            logging.info(f"平仓结果:{json.dumps(order)}")
            self.d.close_order(params, price, profit)
            del self.positions[symbol]
            # return order
        except ClientError as error:
            msg = "平仓失败 status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
            self.d.error(msg)
            logging.error(msg)
            return None

    # 监控交易对的K线数据
    def monitor_kline(self):
        for symbol in self.symbols:
            df = self.get_klines(symbol, self.interval)
            df = self.calculate_macd(df)
            df = self.detect_crosses(df)

            # 计算涨幅和成交量变化
            recent_close = df['close'].iloc[-1]
            previous_close = df['close'].iloc[-2]
            price_change_percent = (recent_close - previous_close) / previous_close * 100
            recent_volume = df['volume'].iloc[-1]
            average_volume = df['volume'].iloc[-20:].mean()

            if recent_volume == 0 or average_volume == 0:
                logging.error(f"{symbol}成交量为0")
                continue

            volume = recent_volume / average_volume

            # 检查当前时刻是否是金叉或死叉
            current_golden_cross = df['golden_cross'].iloc[-1]
            current_death_cross = df['death_cross'].iloc[-1]

            # 是否持仓
            if symbol in self.positions:
                logging.info(
                    f"当前存在持仓: {symbol}{self.positions[symbol]} 当前价:{recent_close} Gold::{current_golden_cross} Death:{current_death_cross}"
                )
                open_price = self.positions[symbol]['entry_price']

                # 止盈
                if self.positions[symbol]['side'] == 'BUY' and recent_close >= open_price * 1.01:
                    self.stop_price_order(symbol, 'SELL', recent_close, True)
                    continue

                if self.positions[symbol]['side'] == 'SELL' and recent_close <= open_price * 0.99:
                    self.stop_price_order(symbol, 'BUY', recent_close, True)
                    continue

                # 判断止损条件
                # 5分钟判断一次
                #  金叉死叉  或者 下一根k线 满足条件
                now = datetime.now()

                # 上五分钟开盘价和本五分钟收盘价
                pre_open_price = df['open'].iloc[-2]
                now_close_price = df['close'].iloc[-1]

                if now.minute % 5 == 4:
                    if self.positions[symbol]['side'] == 'BUY':
                        if not self.positions[symbol]['check_open_price'] and now_close_price < pre_open_price:
                            self.stop_price_order(symbol, 'SELL', recent_close, False)
                            continue

                        self.positions[symbol]['check_open_price'] = True

                        if current_death_cross:
                            logging.info(f"死叉止损:{symbol}")
                            self.stop_price_order(symbol, 'SELL', recent_close, False)
                            continue
                    elif self.positions[symbol]['side'] == 'SELL':
                        if not self.positions[symbol]['check_open_price'] and now_close_price > pre_open_price:
                            self.stop_price_order(symbol, 'BUY', recent_close, False)
                            continue

                        self.positions[symbol]['check_open_price'] = True

                        if current_golden_cross:
                            logging.info(f"金叉止损:{symbol}")
                            self.stop_price_order(symbol, 'BUY', recent_close, False)
                            continue
                continue

            if len(self.positions) >= self.maxPositionCount:
                self.d.normal(f"当前持仓数量达到最大值: {self.maxPositionCount}")
                logging.info(f"当前持仓数量达到最大值: {self.maxPositionCount}")
                return

            # 判断交易信号
            if price_change_percent >= 1.6 and volume >= 3 and current_golden_cross:
                self.place_order(symbol, 'BUY', recent_close)
            elif price_change_percent <= -1.6 and volume >= 3 and current_death_cross:
                self.place_order(symbol, 'SELL', recent_close)

    def init_log(self):
        # 配置日志记录器
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        # 定义日志文件的格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        # 创建TimedRotatingFileHandler，设置文件名、时间间隔和备份数量
        handler = TimedRotatingFileHandler('app.log', when='midnight', interval=1, backupCount=7)
        # 设置日志文件的格式
        handler.setFormatter(formatter)

        # 将处理器添加到日志记录器
        logger.addHandler(handler)

    def notify_balance(self):
        try:
            res = self.client.balance()
            for info in res:
                if info['asset'] == 'USDT':
                    self.d.normal(f"余额:{info['balance']} 未实现盈亏:{info['crossUnPnl']}")
        except ClientError as error:

            msg = "获取余额信息失败 status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
            self.d.error(msg)
            logging.error(msg)

    def init_config(self):
        # 打开配置文件并加载内容
        with open("config.json", 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        self.symbols = config_data['symbols']
        self.maxPositionCount = config_data['maxPositionCount']
        self.costPerOrder = config_data['costPerOrder']
        self.key = config_data['key']
        self.secret = config_data['secret']


if __name__ == "__main__":
    # place_order('BTCUSDT', 'BUY', 69914)
    # stop_price_order('BTCUSDT', 'SELL')
    # notify_balance()
    trade = Trade()
    i = 0
    while True:
        try:
            logging.info(f"运行正常")
            # 每小时通报余额
            if i % 12 == 0:
                trade.notify_balance()

            trade.monitor_kline()
            time.sleep(60)  # 每1分钟运行一次
        except Exception as e:
            msg = f"运行异常: {e}"
            logging.info(msg)
            trade.d.error(msg)
            time.sleep(60)  # 每1分钟运行一次
