import requests

url = 'http://stareabyss.top:5000/faa_server/data_upload/battle_drops'

try:
    response = requests.head(url, timeout=5)
    response.raise_for_status()
    print(f"路由 {url} 可达，状态码：{response.status_code}")
except requests.exceptions.Timeout:
    print("请求超时")
except requests.exceptions.HTTPError as err:
    print(f"HTTP 错误: {err}")
except requests.exceptions.ConnectionError:
    print("连接错误")
except requests.exceptions.RequestException as e:
    print(f"请求异常: {e}")
