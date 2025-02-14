import argparse
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from pathlib import Path
import re
import random
import json
import os, sys

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

# Step 2: 生成解密字体和加密文本（仅处理汉字）
def generate_encryption(input_txt_path, trimmed_font_path, output_encrypted_txt, output_decrypt_font, skip_set_path=None, seed=42):
    # 提取文本内容
    with open(input_txt_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 提取唯一汉字集合
    chinese_char_set = sorted(set(re.findall(r'[\u4e00-\u9fff]', content)))

    # 验证字符集合非空
    if not chinese_char_set:
        raise ValueError("No Chinese characters found in the input text.")

    # 如果有跳过字符集，则加载并跳过指定的汉字
    skip_char_set = set()
    if skip_set_path:
        with open(skip_set_path, 'r', encoding='utf-8') as file:
            skip_char_set = set(re.findall(r'[\u4e00-\u9fff]', file.read()))

    # 移除跳过的汉字
    chinese_char_set = [char for char in chinese_char_set if char not in skip_char_set]

    if not chinese_char_set:
        raise ValueError("No Chinese characters available for encryption after skipping.")

    # 生成随机映射
    shuffled_chars = chinese_char_set[:]
    random.seed(seed)
    random.shuffle(shuffled_chars)
    char_map = dict(zip(chinese_char_set, shuffled_chars))
    reverse_char_map = {v: k for k, v in char_map.items()}

    # 替换文本中的汉字
    def encrypt_char(c):
        return char_map.get(c, c)  # 汉字加密，非汉字保持原样

    encrypted_text = ''.join(encrypt_char(c) for c in content)

    encrypted_dir = os.path.dirname(output_encrypted_txt)
    font_dir = os.path.dirname(output_decrypt_font)

    if font_dir:
        os.makedirs(font_dir, exist_ok=True)

    if encrypted_dir:
        os.makedirs(encrypted_dir, exist_ok=True)

    with open(output_encrypted_txt, 'w', encoding='utf-8') as file:
        file.write(encrypted_text)

    # 修改字体映射（仅对汉字进行映射调整）
    font = TTFont(trimmed_font_path)
    cmap_table = font['cmap'].getcmap(3, 1)
    cmap = cmap_table.cmap
    new_cmap = {ord(k): cmap[ord(v)] for k, v in reverse_char_map.items() if ord(v) in cmap}
    cmap_table.cmap = new_cmap
    font.save(output_decrypt_font)

def main():
    base_path = os.path.abspath(sys.argv[0])
    base_dir = os.path.dirname(base_path)

    msyh_path = os.path.join(base_dir, "msyh.ttc")
    trim_path = os.path.join(base_dir, "trim.ttc")

    parser = argparse.ArgumentParser(description="Font and text encryption tool.")
    parser.add_argument("-f", "--file", required=True, help="Path to the input text file.")
    parser.add_argument("-s", "--save", required=True, help="Path to the output encrypted text file.")
    parser.add_argument("-t", "--woff", required=True, help="Path to the output decryption font file.")
    parser.add_argument("--skip-set", help="Path to a text file containing characters to skip from encryption.")

    args = parser.parse_args()

    trim_font(msyh_path, trim_path, args.file)
    generate_encryption(args.file, trim_path, args.save, args.woff, skip_set_path=args.skip_set)

if __name__ == "__main__":
    main()
