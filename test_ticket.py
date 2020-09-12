import unittest
from ticket import XiHuSportsReserceTicker
import time


class MyTestCase(unittest.TestCase):
    def test_something(self):
        res = XiHuSportsReserceTicker.choose_reserve_date([5])
        if not res:
            self.assertEqual(res, str(int(time.time())))


if __name__ == '__main__':
    unittest.main()
