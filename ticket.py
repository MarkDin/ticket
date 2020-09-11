# -*- coding: utf-8 -*-
import datetime
import ssl
import warnings
from bs4 import BeautifulSoup
import requests
from lxml import etree
import re
from functools import reduce
warnings.filterwarnings("ignore")
ssl._create_default_https_context = ssl._create_unverified_context

headers = {
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-User": "?1",

    "User-Agent": "android Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36 QBCore/4.0.1301.400 QQBrowser/9.0.2524.400 Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2875.116 Safari/537.36 NetType/WIFI MicroMessenger/7.0.5 WindowsWechat",
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

    def reserve(self, url: str, **data):
        ...

    def send_email(self, msg: str):
        ...


class XiHuSportsReserceTicker(ReserveTicket):
    """
    西湖文体中心可预约近五天场地
    """
    cookies = {
        "WECHAT_OPENID": "oAKYc0w3IFGnl7YpOMgmg2ciTQkM",
        "PHPSESSID": "qjikpv1ravhdbefna2oliikoc5",
        "UM_distinctid": "17430ae1019197-02fa33b10717a8-1051275-1fa400-17430ae101a4d5",
    }

    def __init__(self):
        self.host = 'http://xihuwenti.juyancn.cn'
        self.ticket_info_suffix = '/wechat/venue/details?id=6&cid=12&time=%s'
        super().__init__()

    @staticmethod
    def choose_reserve_date(day: int) -> str:
        timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(
            "2020-8-16 00:00:00", "%Y-%m-%d %H:%M:%S"))
        return str(int(timestamp))

    def get_response(self, timestamp) -> str:
        url = self.host + self.ticket_info_suffix % self.choose_reserve_date(6)
        response = requests.get(url, headers=headers, verify=False)
        # print(response.text)
        return response.text

    @staticmethod
    def char_to_digit(ch: str):
        a, b = ch.split(".")
        a = int(a)
        b = int(b)/pow(10, len(b))
        return a + b

    def parse_ticket_info(self, ticket_info_html: str) -> list:
        soup = BeautifulSoup(ticket_info_html, 'lxml')
        li_list = soup.find_all("li", class_="a-default can-select")
        # print(li_list)
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

    def filter_by_time_and_count(self, selectable: list, start_time, end_time, reserve_count):
        res = list(filter(lambda x: int(
            x["end_time"].split(":")[0]) < end_time, selectable))
        res = list(filter(lambda x: int(
            x["start_time"].split(":")[0]) > start_time, res))
        return res[:reserve_count]

    def gen_data(self, ticket_info_html: str, res: list):
        # 计算所需参数
        show_id = re.findall(r"show_id = '(.*?)';", ticket_info_html)[0]
        date = re.findall(r"date = '(.*?)';", ticket_info_html)[0]

        data_ = [r["id"]+','+r["start_time"]+',' + r["end_time"] for r in res]
        total_fee = reduce(
            lambda x, y: x["total_fee"]+y["total_fee"], res) if len(res) > 1 else res[0]["total_fee"]
        money = reduce(lambda x, y: x["money"]+y["money"],
                       res) if len(res) > 1 else res[0]["money"]
        # data = {
        #     "show_id": show_id or '505',
        #     "date": date,
        #     "data[]": data_,
        #     "money": str(money)+"元",  # money比total_fee多一个`元`
        #     "tota_fee": round(total_fee, 2),  # 四舍五入两位小数
        # }
        data = {
            "show_id": '505',
            "date": "2020-08-31",
            "data[]": "81,14:00,15:00",
            "money": "50.00元",  # money比total_fee多一个`元`
            "tota_fee": "50.00",  # 四舍五入两位小数
        }
        print(data)
        return data

    def gen_order_url():
        # WECHAT_OPENID=oAKYc0w3IFGnl7YpOMgmg2ciTQkM
        url = " /wechat/order/index?show_id=505&param="

    @staticmethod
    def gen_order_data(p):
        url = "/wechat/order/add"
        data = {
            "username": "丁",
            "show_id": "505",
            "id_card": "430722199704105896",
            "mobile": "15200689458",

            "param": p,

        }

        host = "https://xihuwenti.juyancn.cn"
        res = requests.post(host+url, headers=headers,
                            cookies=cookies, data=data, verify=False)
        print(res.text)
        print(res.json())
        # respnse = {"code":0,"msg":"46865","pay":0}

    def payment(self):
        url = "https://xihuwenti.juyancn.cn/wechat/buyticket/pay?orderid=46865"


def test():
    data = {
        "show_id": '505',
        "date": "2020-08-31",
        "data[]": "81,14:00,15:00",
        "money": "50.00元",  # money比total_fee多一个`元`
        "tota_fee": "50.00",  # 四舍五入两位小数
    }
    res = requests.post(
        "https://xihuwenti.juyancn.cn/wechat/product/save", data=data, verify=False)
    print(res.text)
    print(res.json())
    return res.json()["msg"]


if __name__ == "__main__":
    # host = "http://xihuwenti.juyancn.cn"
    # url = "/wechat/order/index?show_id=505&param=eyJkYXRlIjoiMjAyMC0wOC0yOCIsInBlcmlvZCI6WyI4MCwxMzowMCwxNDowMCJdLCJtb25leSI6NTAsInRvdGFsX2ZlZSI6NTB9"
    cookies = {
        "WECHAT_OPENID": "oAKYc0w3IFGnl7YpOMgmg2ciTQkM",
    }
    # res = requests.get(host+url, headers=headers,
    #                        cookies=cookies, verify=False)
    # print(res.text)
    # print(res.json())

    param = test()
    p = XiHuSportsReserceTicker()
    p.gen_order_data(param)

'''
    获取param参数 param其实就是一个加密过的包含场地预定信息的token
    url = "https://xihuwenti.juyancn.cn/wechat/product/save" 
    {
        "show_id": '505',
        "date": "2020-08-31",
        "data[]": "81,14:00,15:00",
        "money": "50.00元",  # money比total_fee多一个`元`
        "tota_fee": "50.00",  # 四舍五入两位小数
    }
    填写个人信息 提交订单
    url="/wechat/order/add"
    data = {
            "username": "丁",
            "show_id": "505",
            "id_card": "430722199704105896",
            "mobile": "15200689458",

            "param": p,

        }
'''

