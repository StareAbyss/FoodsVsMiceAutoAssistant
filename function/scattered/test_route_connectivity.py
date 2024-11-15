import requests


def test_route_connectivity(url=None, expected_checksum=None):
    """测试输入的url是否是有效的"""

    if not url:
        url = 'http://stareabyss.top:5000/faa_server/data_upload/battle_drops'

    if not expected_checksum:
        expected_checksum = 'StareAbyss is so cool'

    try:
        # 发送 HEAD 请求
        response = requests.head(url, timeout=1.5)
        response.raise_for_status()  # 抛出 HTTPError 异常，如果响应的状态码不是 200

        # 检查响应头中是否存在 X-Check-Sum 头部
        checksum = response.headers.get('X-Check')

        if checksum == expected_checksum:
            return True, f"路由 {url} 可达，状态码：{response.status_code}，校验文本正确：{checksum}"
        else:
            return False, f"路由 {url} 可达，状态码：{response.status_code}，但校验文本不匹配：预期 {expected_checksum}，实际 {checksum}"

    except requests.exceptions.Timeout:
        return False, "请求超时"
    except requests.exceptions.HTTPError as err:
        return False, f"HTTP 错误: {err}"
    except requests.exceptions.ConnectionError:
        return False, "连接错误"
    except requests.exceptions.RequestException as e:
        return False, f"请求异常: {e}"


if __name__ == "__main__":
    # url = 'https://www.baidu.com'
    result = test_route_connectivity()
    print(result[0])
    print(result[1])
