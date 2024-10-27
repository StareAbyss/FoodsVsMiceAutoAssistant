import xml.etree.ElementTree as ET

import requests

from function.globals.get_paths import PATHS


# 下载并保存图片的函数
def download_and_save_image(image_id, image_name):
    print("\nid十六进制:{} id十进制:{} 名称:{}".format(image_id, int(image_id, 16), image_name))

    for n in range(6):
        # 下载图像
        image_url = "https://q.ms.huanlecdn.com/4399/cdn.123u.com/images/1/{}/{}.png?1.01012346".format(n, image_id)

        response = requests.get(image_url)

        if response.status_code == 200:
            file_name = "{}\\原始资源\\{}\\{}.png".format(PATHS["image"]["item"], n, image_name)
            with open(file_name, 'wb') as file:
                file.write(response.content)
            print("{}次尝试,已下载并保存图片到文件夹到对应序号".format(n))
        else:
            print("{}次尝试,下载图片失败".format(n))


def main():
    # 读取XML文件
    tree = ET.parse('market_item.xml')
    root = tree.getroot()

    # 遍历获取Items
    for item in root.findall('item'):
        if item is not None:
            download_and_save_image(
                image_id=item.get('i_id'),
                image_name=item.get('i_name')
            )


if __name__ == '__main__':
    main()
