from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from pathlib import Path
import re
import random
import json

# Step 1: 裁剪文字文件，只保留必须的文本，减少大小
def trim_font(input_font_path, output_font_path, input_text_path):
    # 加载字体文件
    font = TTFont(input_font_path, fontNumber=0) # ttc类型字体需要指定fontNumber

    # 创建 Subsetter 对象
    options = Options()
    options.ignore_missing_glyphs = True  # 忽略缺少的字符
    subsetter = Subsetter(options=options)

    # 指定需要包含的字符
    subsetter.populate(text=Path(input_text_path).read_text(encoding="utf-8"))

    # 裁剪字体文件
    subsetter.subset(font)

    # 保存裁剪后的字体
    font.save(output_font_path)
    print(f"Subsetted font saved to: {output_font_path}")

# Step 2: 生成解密字体和加密文本（仅处理汉字）
def generate_encryption(input_txt_path, trimmed_font_path, output_encrypted_txt, output_decrypt_font, mapping_output_path, seed=42):
    # 提取文本内容
    with open(input_txt_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 提取唯一汉字集合
    chinese_char_set = sorted(set(re.findall(r'[\u4e00-\u9fff]', content)))

    # 验证字符集合非空
    if not chinese_char_set:
        raise ValueError("No Chinese characters found in the input text.")

    # 生成随机映射
    shuffled_chars = chinese_char_set[:]
    random.seed(seed)
    random.shuffle(shuffled_chars)
    char_map = dict(zip(chinese_char_set, shuffled_chars))
    reverse_char_map = {v: k for k, v in char_map.items()}

    # 保存映射表到文件，用于Debug
    with open(mapping_output_path, 'w', encoding='utf-8') as file:
        json.dump({"char_map": char_map, "reverse_char_map": reverse_char_map}, file, ensure_ascii=False, indent=4)
    print(f"Mapping table saved to {mapping_output_path}")

    # 替换文本中的汉字
    def encrypt_char(c):
        return char_map.get(c, c)  # 汉字加密，非汉字保持原样

    encrypted_text = ''.join(encrypt_char(c) for c in content)
    with open(output_encrypted_txt, 'w', encoding='utf-8') as file:
        file.write(encrypted_text)
    print(f"Encrypted text saved to {output_encrypted_txt}")

    # 修改字体映射（仅对汉字进行映射调整）
    font = TTFont(trimmed_font_path)
    cmap_table = font['cmap'].getcmap(3, 1)
    cmap = cmap_table.cmap
    new_cmap = {ord(k): cmap[ord(v)] for k, v in reverse_char_map.items() if ord(v) in cmap}
    cmap_table.cmap = new_cmap
    font.save(output_decrypt_font)
    print(f"Decryption font saved to {output_decrypt_font}")

# Step 3: 主函数调用
def main():
    # 输入与输出路径
    input_font_path = "msyh.ttc" # 这是微软雅黑字体, 类型是ttc
    input_txt_path = "input.txt"

    trimmed_font_path = "trimmed_font.ttf"
    output_encrypted_txt = "encrypted_text.txt"
    output_decrypt_font = "decrypt_font.woff"
    mapping_output_path = "font_mapping.json"

    # 执行裁剪字体
    trim_font(input_font_path, trimmed_font_path, input_txt_path)

    # 生成加密文本和解密字体，并保存映射表
    generate_encryption(input_txt_path, trimmed_font_path, output_encrypted_txt, output_decrypt_font, mapping_output_path, seed=42)

# 解密并生成解密文本，debug用
def decrypt_text(encrypted_txt_path, mapping_path, output_decrypted_txt):
    # 加载加密文本
    with open(encrypted_txt_path, 'r', encoding='utf-8') as file:
        encrypted_text = file.read()
    
    # 加载映射表
    with open(mapping_path, 'r', encoding='utf-8') as file:
        mapping_data = json.load(file)
    reverse_char_map = mapping_data.get("reverse_char_map", {})
    
    # 替换加密文本中的汉字
    def decrypt_char(c):
        return reverse_char_map.get(c, c)  # 如果字符在映射表中，替换为原文；否则保持原样
    
    decrypted_text = ''.join(decrypt_char(c) for c in encrypted_text)

    # 保存解密文本
    with open(output_decrypted_txt, 'w', encoding='utf-8') as file:
        file.write(decrypted_text)
    print(f"Decrypted text saved to {output_decrypted_txt}")


# 加密并生成加密文本，debug用
def encrypt_text(raw_txt, mapping_path, output_encrypted_txt):
    # 加载原始文本
    with open(raw_txt, 'r', encoding='utf-8') as file:
        encrypted_text = file.read()
    
    # 加载映射表
    with open(mapping_path, 'r', encoding='utf-8') as file:
        mapping_data = json.load(file)
    char_map = mapping_data.get("char_map", {})
    
    # 替换加密文本中的汉字
    def encrypt_char(c):
        return char_map.get(c, c)  # 如果字符在映射表中，替换为原文；否则保持原样
    
    encrypted_txt = ''.join(encrypt_char(c) for c in encrypted_text)

    # 保存解密文本
    with open(output_encrypted_txt, 'w', encoding='utf-8') as file:
        file.write(encrypted_txt)
    print(f"Encrypted text saved to {output_encrypted_txt}")

def solve(font_path):
    font = TTFont(font_path)
    cmap_table = font['cmap'].getcmap(3,1)
    with open('solve.json', 'w', encoding='utf-8') as file:
        json.dump({k : v for k, v in cmap_table.cmap.items()}, file, ensure_ascii=False, indent=4)