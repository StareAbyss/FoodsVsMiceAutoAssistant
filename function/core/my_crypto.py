import wmi
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64



# 获取机器码（主板序列号）
def get_machine_code():
    c = wmi.WMI()
    for item in c.Win32_BaseBoard():
        return item.SerialNumber
    return None

# 根据机器码生成密钥
def generate_key_from_machine_code(machine_code):
    key = hashlib.sha256(machine_code.encode()).digest()
    return key[:16]  # 截取前 16 字节作为密钥

# 数据加密
def encrypt_data(data):
    key=generate_key_from_machine_code(get_machine_code())
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv
    encrypted_data = cipher.encrypt(pad(data.encode(), AES.block_size))
    # 将 IV 和加密数据拼接后进行 Base64 编码
    encrypted_base64 = base64.b64encode(iv + encrypted_data).decode('utf-8')
    return encrypted_base64

# 数据解密
def decrypt_data(encrypted_data_base64):
    # 解码 Base64 字符串为原始加密数据
    key=generate_key_from_machine_code(get_machine_code())
    encrypted_data = base64.b64decode(encrypted_data_base64)
    iv = encrypted_data[:16]  # 提取 IV
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(encrypted_data[16:]), AES.block_size)
    return decrypted_data.decode('utf-8')



