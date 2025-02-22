import base64
import hashlib

import wmi
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# 获取机器码
def get_machine_code():
    try:
        c = wmi.WMI()

        # 1 尝试获取主板序列号
        baseboard = c.Win32_BaseBoard()
        if baseboard and baseboard[0].SerialNumber and baseboard[0].SerialNumber.strip():
            return baseboard[0].SerialNumber.strip()

        # 2 主板序列号无效？尝试获取 UUID（适用于云服务器）
        system_product = c.Win32_ComputerSystemProduct()
        if system_product and system_product[0].UUID and system_product[0].UUID.strip():
            return system_product[0].UUID.strip()

        # 3 UUID 无效？尝试获取 BIOS 序列号
        bios = c.Win32_BIOS()
        if bios and bios[0].SerialNumber and bios[0].SerialNumber.strip():
            return bios[0].SerialNumber.strip()

        # 4 BIOS 序列号无效？尝试获取 CPU 序列号
        processor = c.Win32_Processor()
        if processor and processor[0].ProcessorId and processor[0].ProcessorId.strip():
            return processor[0].ProcessorId.strip()

        # 5 CPU ID 也无效？尝试获取第一个硬盘序列号（不一定唯一）
        disk = c.Win32_DiskDrive()
        if disk and disk[0].SerialNumber and disk[0].SerialNumber.strip():
            return disk[0].SerialNumber.strip()
        
    except Exception as e:
        print(f"[ERROR] 获取机器码失败: {e}")

    return None  # 没有可用的机器码

# 测试代码
print(get_machine_code())


# 根据机器码生成密钥
def generate_key_from_machine_code(machine_code):
    key = hashlib.sha256(machine_code.encode()).digest()
    return key[:16]  # 截取前 16 字节作为密钥


# 数据加密
def encrypt_data(data):
    key = generate_key_from_machine_code(get_machine_code())
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv
    encrypted_data = cipher.encrypt(pad(data.encode(), AES.block_size))
    # 将 IV 和加密数据拼接后进行 Base64 编码
    encrypted_base64 = base64.b64encode(iv + encrypted_data).decode('utf-8')
    return encrypted_base64


# 数据解密
def decrypt_data(encrypted_data_base64):
    # 解码 Base64 字符串为原始加密数据
    key = generate_key_from_machine_code(get_machine_code())
    encrypted_data = base64.b64decode(encrypted_data_base64)
    iv = encrypted_data[:16]  # 提取 IV
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(encrypted_data[16:]), AES.block_size)
    return decrypted_data.decode('utf-8')
