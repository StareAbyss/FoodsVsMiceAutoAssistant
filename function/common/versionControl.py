

import requests
import time
import json
import urllib.parse
import re

def get_current_timestamp():
    """
    返回当前的时间戳（以秒为单位）。
    """
    timestamp = int(time.time()*1000)
    return timestamp


# 这两个参数会变化，但其实可以乱填
# __dt 属性为页面时间，由以下函数生成，即当前时间减去页面打开的时时间
# function r() {
#         return window.performance && window.performance.timing ? Date.now() - window.performance.timing.navigationStart : 0
#     }

# __t: 1724056613238 当前时间戳,毫秒级，由Date.now()生成





def get_quark_token(pwd_id):
    '''
    pwd_id：文件夹id，从分享链接获取
    '''
    # headers其实有没有都无所谓
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Content-Type': 'application/json',
        # 'Cookie': '_UP_A4A_11_=wb9051514c2d46fc82423965004fa6e5; b-user-id=47ada3b7-ff01-7c0f-2781-3cdf6fb563da; cna=4q8aHzvztDgCASRwHRmyzLm+; _UP_30C_6A_=st9676201b81z66go4gtxrny5v3k9t29; _UP_TS_=sg11439e931f7885684d7d263955275a7b1; _UP_E37_B7_=sg11439e931f7885684d7d263955275a7b1; _UP_TG_=st9676201b81z66go4gtxrny5v3k9t29; _UP_335_2B_=1; xlly_s=1; _UP_D_=pc; tfstk=fRuZG4OqPFLabam0LJa4Tf18S_zTkzp7Iqwbijc01R2glhnqYjGy6SMsi-o4Kjei55xAt6VziO2DXSb4LJDn1NwbS-fqhjis3jdTi-Dm3-i6AUGt6rUDFr8WPfCJ0UOZ7rXjtXJAuq9WPUGi6rUDFLOvKFI84S40slbgKBP8Kt40IoXhx723nr4mnXDM2-2587rMao5Ap4n__lyPlJ7VuINab8cgLWFK8EEaEf2FoLsTpAw4p4vBYXnnjANK3UJUkvnmnSkhKKZtiDkU_A9PH-gt1qys_hvtTy2ZIloeZGFEOVlqmkRMSXzaQugEIssT7mDtulnNMQh3Svn8elxppWusPoy8Y9viOXyg4mk6pZ2s4XDUV26CPrHKmxVqKOSyvtFn5n0xbtj4jWFUFBRh5lDTv46X5usADlnLT8O96iIYjWFUFBRFDiETyWyW6CC..; isg=BOHh3PdCI3PmdI9XcoVOWjyA8K37jlWAlrWKtEO23ehHqgF8i95lUA_oDN4see24',
        'Origin': 'https://pan.quark.cn',
        'Referer': 'https://pan.quark.cn/',
        'Sec-Ch-Ua': '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0'
    }


    # pwd_id是文件id，从文件分享链接可以获取，https://pan.quark.cn/s/76232a322cce
    # 虽然我也不知道为什么获取cookie需要文件id，好奇怪的设定

    url=f'https://drive-h.quark.cn/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc&uc_param_str=&__dt=1200&__t={get_current_timestamp()}'
    data = {
        'passcode': '',
        'pwd_id': pwd_id
    }
    # 一定要把data传给json
    response=requests.post(url,headers=headers,json=data)
    res_json=json.loads(response.text)
    token=res_json['data']['stoken']
    token = urllib.parse.quote(token) #对token进行URL编码，将特殊字符转换为 % 后跟两个十六进制数字的格式
    return token


def get_filename(pwd_id:str):
    '''
    参数有一个
    pwd_id：文件夹id，从分享链接获取
    
    返回值：文件名
    
    '''
    
    # 以下url的参数中，pwd_id、pdir_fid、stoken比较重要，其他的好像都可以不填
    # pdir_fid应该是文件夹id的，应该也是固定的
    url=f'https://drive-h.quark.cn/1/clouddrive/share/sharepage/detail?pr=ucpro&fr=pc&uc_param_str=&pwd_id={pwd_id}&stoken={get_quark_token(pwd_id)}&pdir_fid=0&force=0&_page=1&_size=50&_fetch_banner=0&_fetch_share=0&_fetch_total=1&_sort=file_type:asc,updated_at:desc&__dt=818&__t={get_current_timestamp()}'

    # headers其实有没有都无所谓
    headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
    }
    response=requests.get(url=url,headers=headers)

    match = re.search(r'"file_name":\s*"([^"]*)"', response.text)
    
    file_name=''
    if match:
        file_name = match.group(1)
        # print("file_name:", file_name)
    else:
        print("没有找到 file_name")
    return file_name

def get_version(pwd_id:str):
    '''
    从夸克网盘获取FAA的版本号
    
    pwd_id：文件夹id，从分享链接获取
    
    返回值：版本号，例如v1.5.0
    '''
    file_name=get_filename(pwd_id)
    # 文件夹名为FAA-v1.5.0fix的格式，版本号为v1.5.0fix，所以前4个字符不包含在版本号内
    version=file_name[4:]
    
    return version

def is_need_update(pwd_id:str):
    
    '''
    从特定的夸克网盘文件夹获取是否需要强制更新的信息
    
    pwd_id：文件夹id，从分享链接获取
    
    返回值：bool类型，为True时表示需要强制更新
    '''
    file_name=get_filename(pwd_id)
    if file_name!='':
        return file_name=='update'
    else: # 如果因为爬虫代码失效而获取失败，需要返回False，否则会影响软件的正常使用
        return False


print(get_version('76232a322cce'))
print(is_need_update('fcf203055a00'))
