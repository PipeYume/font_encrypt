import argparse
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from pathlib import Path
from typing import Optional, Set, Dict, Union
import re
import random
import json
import os, sys
from uuid import uuid4
import copy

PathLike = Union[str, os.PathLike]

class FontEncryptor:
    font_path: Path
    pattern: str
    skip_char_set: Set[str]
    seed: int

    def __init__(self, font_path: PathLike, pattern: Optional[str]=r'[\u4e00-\u9fff]', skip_str: str="", seed: int=42) -> None:
        self.font_path = Path(font_path)
        if pattern:
            self.pattern = pattern
        else:
            self.pattern = r"[\s\S]"

        if skip_str:
            self.skip_char_set = self.get_valid_char_set(skip_str)
        else:
            self.skip_char_set = set()

        self.seed = seed
        # 创建 Subsetter 对象
        options = Options()
        options.ignore_missing_glyphs = True  # 忽略缺少的字符
        self.subsetter = Subsetter(options=options)
        pass

    def get_valid_char_set(self,text: str):
        char_set = set(re.findall(self.pattern, text))
        if not char_set:
            raise ValueError(f"无有效字符")
        return char_set

    def trim_font(self, text: str, fontNumber=0):
        font = TTFont(self.font_path, fontNumber = fontNumber) # ttc类型字体需要指定fontNumber
        char_set = self.get_valid_char_set(text) - self.skip_char_set
        self.subsetter.populate(text= "".join(c for c in char_set if c) )
        self.subsetter.subset(font)
        return font

    def generate_char_map(self, text: str):
        char_set = sorted(self.get_valid_char_set(text) - self.skip_char_set)
        # 生成随机映射
        shuffled_chars = list(char_set)
        random.seed(self.seed)
        random.shuffle(shuffled_chars)
        char_map:dict[str, str] = dict(zip(char_set, shuffled_chars))
        return char_map

    def encrypt_text(self, text: str, char_map: Dict[str, str]):
        encrypt_char = lambda c : char_map.get(c, c) # 如果字符在映射表中，替换为原文；否则保持原样
        return ''.join(encrypt_char(c) for c in text)

    def decrypt_text(self, text: str, char_map: Dict[str, str]):
        decrypt_map = {v: k for k, v in char_map.items()}
        decrypt_char = lambda c : decrypt_map.get(c, c)
        return ''.join(decrypt_char(c) for c in text)

    def generate_decrypt_font(self, font: TTFont, char_map: Dict[str, str]):
        new_font = copy.deepcopy(font)
        decrypt_map = {v: k for k, v in char_map.items()}
        cmap_table = new_font['cmap'].getcmap(3, 1) # type: ignore
        cmap = cmap_table.cmap
        new_cmap = {ord(k): cmap[ord(v)] for k, v in decrypt_map.items() if ord(v) in cmap}
        cmap_table.cmap = new_cmap
        return new_font

def main():
    base_path = os.path.abspath(sys.argv[0])
    base_dir = os.path.dirname(base_path)

    font_path = os.path.join(base_dir, "msyh.ttc")
    skip_char_path = os.path.join(base_dir, "traditional_simplified_charset.txt")

    parser = argparse.ArgumentParser(description="Font and text encryption tool.")
    parser.add_argument("-e", "--encrypt", action="store_true", help="Encryption mode (Default)")
    parser.add_argument("-d", "--decrypt", action="store_true", help="Decryption mode")
    parser.add_argument("-f", "--file", required=True, help="Path to the input text file")
    parser.add_argument("-s", "--save", required=True, help="Path to the output text file")
    parser.add_argument("-t", "--woff", help="Path to the output decryption woff font file in ENCRYPTION")
    parser.add_argument("-savemap", "--save-char-map", help="Path to the output char map json in ENCRYPTION")
    parser.add_argument("--seed", help="A random seed for generation of char map in ENCRYPTION")
    parser.add_argument("-map", "--char-map", help="Path to a char map json that will be used in ENCRYPTION or DECRYPTION")
    args = parser.parse_args()

    def write_text(file_path: str, text: str):
        Path(file_path).write_text(text, encoding="utf-8")
    def read_text(file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")

    if args.decrypt:
        if not args.char_map:
            raise ValueError("Decryption mode needs a char map, use `-m` to specify one")
        text = read_text(args.file)
        encryptor = FontEncryptor(font_path, skip_str=read_text(skip_char_path))
        char_map = json.loads(read_text(args.char_map))
        decrypted_text = encryptor.decrypt_text(text, char_map)
        write_text(args.save, decrypted_text)
    else:
        text = read_text(args.file)
        encryptor = FontEncryptor(font_path, skip_str=read_text(skip_char_path))

        # 裁剪字体
        trimmed_font = encryptor.trim_font(text)

        # 生成char map
        if args.char_map:
            char_map = json.loads(read_text(args.char_map))
        else:
            char_map = encryptor.generate_char_map(text)
        if(args.save_char_map):
            write_text(args.save_char_map, json.dumps(char_map,ensure_ascii=False, indent=4))
        # 生成加密文字
        encrypted_text = encryptor.encrypt_text(text, char_map)
        write_text(args.save, encrypted_text)
        # 生成解密字体
        if args.woff:
            if(not args.woff.endswith(".woff")):
                raise ValueError("The output woff font path must be ended with .woff")
            decrypt_font = encryptor.generate_decrypt_font(trimmed_font, char_map)
            decrypt_font.save(args.woff)

if __name__ == "__main__":
    main()
