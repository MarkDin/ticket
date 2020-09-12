# -*- coding: utf-8 -*-
import datetime
import json
import re
import smtplib
import ssl
import sys
import time
import warnings
from collections import defaultdict
from email.mime.text import MIMEText
from traceback import TracebackException
import redis

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
ssl._create_default_https_context = ssl._create_unverified_context

headers = {
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-User": "?1",
    "User-Agent": "android Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/53.0.2785.116 Safari/537.36 QBCore/4.0.1301.400 QQBrowser/9.0.2524.400 Mozilla/5.0 (Windows "
                  "NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2875.116 Safari/537.36 "
                  "NetType/WIFI MicroMessenger/7.0.5 WindowsWechat",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.5;q=0.4",
}
# 场馆预订： /wechat/product/details?id=505&time=0


ra = datetime.datetime.timestamp(datetime.datetime.strptime(
    "2020-8-16 00:00:00", "%Y-%m-%d %H:%M:%S"))


class ReserveTicket(object):
    def __init__(self):
        self.today = datetime.datetime.today()

    def login(self):
        ...

    def get_response(self):
        ...

    def parse_ticket_info(self, ticket_info_html: str):
        ...

    def reserve(self):
        ...

    def send_email(self, msg: str):
        ...


class XiHuSportsReserceTicker(ReserveTicket):
    """
    西湖文体中心可预约近五天场地
    """

    cookies = {
        "WECHAT_OPENID": "oAKYc0w3IFGnl7YpOMgmg2ciTQkM",
        "PHPSESSID": "hoe6qt52uea4orm2mph0n43sd7",
        "UM_distinctid": "17480d12fdd234-03ca781bc224c4-a712a52-41eb0-17480d12fde28e",
    }
    night_ticket_info_suffix = '/wechat/product/details?id=503&time=%s'
    day_ticket_info_suffix = '/wechat/product/details?id=505&time=%s'

    def __init__(self, start_time, end_time, count, reserve_weekdays: list):
        self.start_time = start_time
        self.end_time = end_time
        self.reserve_count = count
        self.host = 'http://xihuwenti.juyancn.cn'
        self.ticket_info_suffix = self.day_ticket_info_suffix
        if start_time >= 18:
            self.ticket_info_suffix = self.night_ticket_info_suffix
        if not reserve_weekdays:
            self.reserve_weekdays = [5, 6]  # 5, 6在场馆预定系统中表示周六, 周日
        else:
            for day in reserve_weekdays:
                if day not in [0, 1, 2, 3, 4, 5, 6]:
                    print("输入时间有误, 0表示周一,6表示周日")
                    self.reserve_weekdays = []
                    return
            self.reserve_weekdays = reserve_weekdays
        super().__init__()

    def run(self):
        print("开始运行")
        global message
        for timestamp in self.choose_reserve_date(self.reserve_weekdays):
            message = []
            html = self.get_response(timestamp)
            # 搜索可以预定的场地
            selectable_list = self.parse_ticket_info(html)
            if not selectable_list:
                print("{}未检测到余票".format(timestamp))
                continue
            # 在可预定的场地中筛选
            selectable_list = self.filter_by_time(
                selectable_list, self.start_time, self.end_time
            )
            if not selectable_list:
                print("{}选择时间内未检测到余票".format(timestamp))
                continue
            can_continue_reserve, res = self.filter_by_count(
                selectable_list, self.start_time, self.end_time, self.reserve_count
            )
            if not can_continue_reserve:
                res = self.filter_by_count_not_continue(res, self.reserve_count) or selectable_list[0]
            # 构造场地预定data
            ticket_info = self.gen_reserve_data(html, res)
            message.append("场地预定成功，信息如下:")
            message.append(json.dumps(ticket_info))
            # 获取预定场地所需的加密的param参数
            param = self.get_param_by_ticket_info(ticket_info)
            if not param:
                print("get_param_by_ticket_info error")
                return False
            # 预定
            flag = self.reserve(param)
            if flag:
                print('\n'.join(message))
                send_email('\n'.join(message), type_=1)
                print("成功预定场地")
                time.sleep(5)
            else:
                print("预定场地失败")
        print("结束运行")

    @staticmethod
    def choose_reserve_date(reserve_weekdays) -> str or None:
        '''
        计算每周六周日的时间戳(字符串)
        '''
        today = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0, 0, 0))
        weekday = today.weekday()
        delta = 0
        res = []
        for reserve_weekday in reserve_weekdays:
            if weekday != reserve_weekday:
                if reserve_weekday < weekday:  # 预订日期在下周
                    reserve_weekday = reserve_weekday + 7
                delta = reserve_weekday - weekday
            if delta >= 5:  # 距离想预订的日期相差超过5天 不可预订
                print("周{}不可预定".format(reserve_weekday+1 if reserve_weekday < 7 else reserve_weekday-6))
                return res
            reserve_datetime = datetime.timedelta(delta) + today
            timestamp = datetime.datetime.timestamp(reserve_datetime)
            res.append(str(int(timestamp)))
        return res

    def get_response(self, timestamp_str) -> str:
        url = self.host + self.ticket_info_suffix % timestamp_str
        response = requests.get(url, headers=headers, verify=False)
        return response.text

    @staticmethod
    def char_to_digit(ch: str):
        a, b = ch.split(".")
        a = int(a)
        b = int(b) / pow(10, len(b))
        return a + b

    def parse_ticket_info(self, ticket_info_html: str) -> list:
        soup = BeautifulSoup(ticket_info_html, 'lxml')
        li_list = soup.find_all("li", class_="a-default can-select")
        selectable = []
        for li in li_list:
            selectable.append(
                {
                    "pos": li.get("data-position"),
                    "start_time": li.get("data-start"),
                    "end_time": li.get("data-end"),
                    "total_fee": self.char_to_digit(li.get("data-cost_price")),
                    "money": int(li.get("data-price")),
                    "text": li.get_text(),
                    "id": li.get("data-hall_id")
                }
            )
        return selectable

    @staticmethod
    def get_hour(t: dict) -> int:
        return int(t["start_time"].split(":")[0])

    def filter_by_count(self, res: list, start_time, end_time, reserve_count):

        d = defaultdict(list)
        # 预订多个连续场次
        for r in res:
            d[self.get_hour(r)].append(r)
        flag = []
        hours = d.keys()
        for i in range(start_time, end_time + 1):
            if i in hours:
                flag.append(1)
            else:
                flag.append(0)
        i = 0
        while i + reserve_count <= len(flag):
            if 0 not in flag[i:i + reserve_count]:
                return True, [d[j + start_time][0] for j in range(i, i+reserve_count)]
            i += 1
        return False, res

    @staticmethod
    def filter_by_time(selectable, start_time, end_time):
        res = list(filter(lambda x: int(
            x["end_time"].split(":")[0]) <= end_time, selectable))
        res = list(filter(lambda x: int(
            x["start_time"].split(":")[0]) >= start_time, res))
        return res

    @staticmethod
    def filter_by_count_not_continue(selectable, count):
        res = []
        t = list()
        for s in selectable:
            if s["start_time"] not in t:
                t.append(s["start_time"])
                res.append(s)
                count -= 1
            if count == 0:
                break
        return res


    def gen_reserve_data(self, ticket_info_html: str, res: list):
        # 计算所需参数
        show_id = re.findall(r"show_id = '(.*?)';", ticket_info_html)[0]
        date = re.findall(r"date = '(.*?)';", ticket_info_html)[0]

        data_ = [r["id"] + ',' + r["start_time"] + ',' + r["end_time"] for r in res]
        total_fee = 0.00
        if len(res) > 1:
            for r in res:
                total_fee += r["total_fee"]
        else:
            total_fee = res[0]["total_fee"]
        money = 0
        if len(res) > 1:
            for r in res:
                money += r["money"]
        else:
            money = res[0]["money"]
        print(total_fee, money)
        data = {
            "show_id": show_id or '505',
            "date": date,
            "data[]": data_,
            "money": str(money) + ".00",
            "total_fee": str(round(total_fee, 1)) + "0元"  # 四舍五入两位小数
        }
        # data = [
        #     ('show_id', show_id or '505'),
        #     ("date", date),
        #     ("money", str(money) + ".00"),
        #     ("total_fee", str(round(total_fee, 1)) + "0元")
        # ]
        # for _ in data_:
        #     data.append(
        #         ("data[]", _)
        #     )
        print("场地信息预定信息：", data)
        return data

    @staticmethod
    def get_param_by_ticket_info(data):
        url = "https://xihuwenti.juyancn.cn/wechat/product/save"
        header_ = headers
        header_["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        res = requests.post(url, headers=header_, data=data, cookies=XiHuSportsReserceTicker.cookies, verify=False)
        return res.json().get("msg")

    @staticmethod
    def reserve(param):
        url = "/wechat/order/add"
        data = {
            "username": "丁",
            "show_id": "505",
            "id_card": "430722199704105896",
            "mobile": "15200689458",
            "param": param,

        }
        host = "https://xihuwenti.juyancn.cn"
        resp = requests.post(host + url, headers=headers,
                             cookies=XiHuSportsReserceTicker.cookies, data=data, verify=False)
        res = resp.json()
        if not res:
            return False
        if res.get("code") == 0 and res.get("msg"):
            return True
        return False
        # respnse = {"code":0,"msg":"46865","pay":0}

    def payment(self):
        url = "https://xihuwenti.juyancn.cn/wechat/buyticket/pay?orderid=46865"


def send_email(mail_body, type_):
    mail_from = 'dingke@lukou.com'
    mail_to = ['1543100966@qq.com']
    # 构造MIMEText对象做为邮件显示内容并附加到根容器
    message = MIMEText(mail_body)

    # 设置根容器属性
    if type_:
        message['Subject'] = '场地预定成功通知'
    else:
        message['Subject'] = "程序异常通知"

    message['From'] = mail_from
    message['To'] = ';'.join(mail_to)
    message['date'] = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    # 用smtp发送邮件
    smtp = smtplib.SMTP_SSL('smtp.exmail.qq.com', 465)
    login_res = smtp.login(mail_from, '199704105896Abc')
    print("login_res: ", login_res)
    smtp.sendmail(mail_from, mail_to, message.as_string())
    if not login_res[0] == 235:
        smtp.quit()
        return False
    smtp.quit()


def main():
    x = XiHuSportsReserceTicker(14, 22, 1, [0])
    global message
    message = []
    try:
        x.run()
    except Exception:
        t = TracebackException(*sys.exc_info(), limit=None).format(chain=True)
        msg = ''.join(t)
        print(msg)
        send_email(msg, type_=0)


if __name__ == "__main__":
    message = []
    main()
