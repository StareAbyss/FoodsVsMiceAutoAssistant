# import requests
#
# # 定义仓库的所有者和名称
# owner = 'example'
# repo = 'project'
#
# # GitHub API URL
# url = f'https://api.github.com/repos/StareAbyss/FoodsVsMiceAutoAssistant/releases/latest'
#
# # 发送 GET 请求
# response = requests.get(url)
#
# # 检查请求是否成功
# if response.status_code == 200:
#     data = response.json()
#     latest_release_tag = data['tag_name']
#     print(f"The latest release tag is: {latest_release_tag}")
# else:
#     print(f"Failed to retrieve the latest release information. Status code: {response.status_code}")

def compare_versions(version1, version2):
    def compare_versions_main():
        # 分解基本版本号
        v1_parts = version1.lstrip('v').split('-')[0].split('.')
        v2_parts = version2.lstrip('v').split('-')[0].split('.')

        # 比较主版本号
        if int(v1_parts[0]) > int(v2_parts[0]):
            return version1
        elif int(v1_parts[0]) < int(v2_parts[0]):
            return version2

        # 比较次版本号
        if int(v1_parts[1]) > int(v2_parts[1]):
            return version1
        elif int(v1_parts[1]) < int(v2_parts[1]):
            return version2

        # 比较修订版本号
        if int(v1_parts[2]) > int(v2_parts[2]):
            return version1
        elif int(v1_parts[2]) < int(v2_parts[2]):
            return version2

        return None

    if version1 == version2:
        return f"您正在使用最新正式版本，真棒!"

    return_value = compare_versions_main()
    if return_value is None:
        if "beta" in version1:
            return f"您正在使用的beta测试版本已被提升为最新正式版本，请放心使用~"

    if return_value == version1:
        # 主要版本号本地领先
        if "beta" in version1:
            return f"您正在使用较新的beta测试版本，感谢测试, 欢迎反馈bug, 请关注群内公告及时更新测试版本!"
        else:
            return f"您正在抢先体验最新正式版本, 太棒了!"

    if return_value == version2:
        if "beta" in version1:
            return f"您正在使用较老的beta测试版本，请务必尽快更新~ 相关BUG将不会受理! 很可能在新版中已修复!"
        else:
            return f"为最新正式版本的抢先体验, 太棒了!"


version1 = 'v1.4.0'
version2 = 'v1.5.0-beta.3'
print(f"您的版本号是:{version1},云端版本号是:{version2}")
print(compare_versions(version1, version2))
