from datetime import datetime
from dingtalkchatbot.chatbot import DingtalkChatbot



class DingTalk:
    def __init__(self, name=''):
        # DingTalk Config
        self.name = name
        webhook = 'https://oapi.dingtalk.com/robot/send?access_token=a911f9efbac27d257b73e19aa6130c50967c0b4e71dd596a8640934450106354'
        secret = 'SEC19c75d0f3df5fb8292d2b091eb5369d7c6043b6c8108d87c3ba267ed2343a07c'
        self.ding = DingtalkChatbot(webhook, secret)

    def normal(self, msg):
        red_msg = '<font color="#dd0000">运行正常</font>'

        now_time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        a = self.ding.send_markdown(
            title=f'{self.name}交易机器人coin',
            text=f'{red_msg}\n\n'
                 f'{msg}\n\n'
                 f'**发送时间:**  {now_time}\n\n',
            is_at_all=True)

    def error(self, msg):
        red_msg = '<font color="#dd0000">运行异常</font>'
        now_time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        self.ding.send_markdown(
            title=f'{self.name}交易机器人coin',
            text=f'{red_msg}\n\n'
                 f'{msg}\n\n'
                 f'**发送时间:**  {now_time}\n\n',
            is_at_all=True)

    def order(self, info, price):
        red_msg = '<font color="#dd0000">开仓</font>'
        now_time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        sub_msg = (f"交易对：<font color='#FFA500'>{info['symbol']}</font>\n\n"
                   f"方向：<font color='#FFA500'>{info['side']}</font>\n\n"
                   f"数量：<font color='#FFA500'>{info['quantity']}</font>\n\n"
                   f"参考价格：<font color='#FFA500'>{price}</font>\n\n"
                   f"<hr>\n\n"
                   )

        self.ding.send_markdown(
            title=f'{self.name}交易机器人coin',
            text=f'{red_msg}\n\n'
                 f'{sub_msg}\n\n'
                 f'**发送时间:**  {now_time}\n\n',
            is_at_all=True)

    def close_order(self, info, price, profit):
        t = '止盈'
        if not profit:
            t = '止损'
        red_msg = f"<font color='#dd0000'>平仓{t}</font>"
        now_time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        sub_msg = (f"交易对：<font color='#FFA500'>{info['symbol']}</font>\n\n"
                   f"方向：<font color='#FFA500'>{info['side']}</font>\n\n"
                   f"参考价格：<font color='#FFA500'>{price}</font>\n\n"
                   f"<hr>\n\n"
                   )

        self.ding.send_markdown(
            title=f'{self.name}交易机器人coin',
            text=f'{red_msg}\n\n'
                 f'{sub_msg}\n\n'
                 f'**发送时间:**  {now_time}\n\n',
            is_at_all=True)

    def volume_alter(self, symbol, b):
        now_time = datetime.now().strftime('%Y.%m.%d %H:%M:%S')
        self.ding.send_markdown(
            title=f' {symbol}',
            text=f'5分钟涨幅大于1.6，成交量大3倍\n\n'
                 f'**交易对:**  {symbol}\n\n'
                 f'**交易量差倍:**  {int(b)}\n\n'
                 f'**发送时间:**  {now_time}\n\n',
            is_at_all=True)

    def normalmacd(self, data):
        if len(data) <= 0:
            return

        msg = ""
        for info in data:
            msg += f"{info['symbol']}  \r\n\r\n"

        self.ding.send_markdown(
            title=f'满足',
            text=f'MACD 的 DIF 小于 0 或 5 日均线上穿 30 日均线\n\n'
                 f'{msg}\n\n',
            is_at_all=True)
