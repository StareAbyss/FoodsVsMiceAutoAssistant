"""
测试领取温馨礼包功能
测试URL请求和异常处理逻辑
"""
import requests
from requests import RequestException


def test_send_request():
    """
    测试发送请求领取温馨礼包的功能

    测试场景:
    1. 正常请求成功
    2. 网络异常/超时
    3. HTTP错误
    4. JSON解析错误
    """

    # 测试参数
    pid = 1
    url = "http://meishi.wechat.123u.com/meishi/gift?openid=ox04QxP5WMoW_lKouFL_qKg5NK7s"

    print(f"开始测试领取温馨礼包功能")
    print(f"Player ID: {pid}")
    print(f"URL: {url}")
    print("-" * 50)

    try:
        # 发送GET请求，设置10秒超时
        print("正在发送请求...")
        r = requests.get(url, timeout=10)

        # 检查HTTP状态码，如果不是200则抛出异常
        r.raise_for_status()

        # 解析JSON响应并获取msg字段
        print("请求成功，正在解析响应...")
        response_data = r.json()

        # 输出结果
        print(f"[{pid}P] 领取温馨礼包情况: {response_data}")
        print("-" * 50)
        print("✓ 测试通过 - 请求成功")

    except requests.exceptions.Timeout:
        # 请求超时
        print(f"[{pid}P] 领取温馨礼包情况: 失败, 请求超时(超过10秒)")
        print("-" * 50)
        print("✗ 测试失败 - 请求超时")

    except requests.exceptions.ConnectionError as e:
        # 连接错误（网络问题、服务器无响应等）
        print(f"[{pid}P] 领取温馨礼包情况: 失败, 欢乐互娱的服务器炸了, {e}")
        print("-" * 50)
        print("✗ 测试失败 - 连接错误")

    except requests.exceptions.HTTPError as e:
        # HTTP错误（状态码不是200）
        print(f"[{pid}P] 领取温馨礼包情况: 失败, HTTP错误, {e}")
        print("-" * 50)
        print("✗ 测试失败 - HTTP错误")

    except requests.exceptions.JSONDecodeError as e:
        # JSON解析错误
        print(f"[{pid}P] 领取温馨礼包情况: 失败, JSON解析错误, {e}")
        print("-" * 50)
        print("✗ 测试失败 - JSON解析错误")

    except KeyError as e:
        # 响应中缺少'msg'字段
        print(f"[{pid}P] 领取温馨礼包情况: 失败, 响应数据格式错误, 缺少msg字段, {e}")
        print("-" * 50)
        print("✗ 测试失败 - 数据格式错误")

    except RequestException as e:
        # 其他requests异常（兜底处理）
        print(f"[{pid}P] 领取温馨礼包情况: 失败, 欢乐互娱的服务器炸了, {e}")
        print("-" * 50)
        print("✗ 测试失败 - 未知请求异常")


if __name__ == "__main__":
    test_send_request()
