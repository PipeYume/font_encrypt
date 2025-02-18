import argparse
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.subset import Subsetter, Options
from fontTools.misc.psCharStrings import T2CharString
from fontTools.cffLib.specializer import programToCommands, commandsToProgram
from pathlib import Path
from typing import Optional, Set, Dict, Union, Iterable
import re
import random
import json
import os, sys, io, base64
import copy

PathLike = Union[str, os.PathLike]

class FontEncryptor:
    font_path: Path
    pattern: str
    '''正则匹配需要加密的字'''
    skip_char_set: Set[str]
    '''跳过不需要加密的字'''
    seed: int

    def __init__(self, font_path: PathLike, pattern: Optional[str]=r'[\u4e00-\u9fff]', skip_str: str="", seed: int=42):
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
        self.subsetter.populate(text=text)
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
        decrypt_font = copy.deepcopy(font)
        decrypt_map = {v: k for k, v in char_map.items()}
        # 获取 cmap 表
        cmap = decrypt_font.getBestCmap()
        glyph_set = decrypt_font.getGlyphSet()
        # 统一处理字形表
        glyph_table = getattr(glyph_set, 'glyfTable', None) or getattr(glyph_set, 'charStrings', None)
        if not glyph_table:
            raise ValueError("字体中不存在有效字形表")
        temp_table = copy.deepcopy(glyph_table)
        # 交换字形
        for char, new_char in decrypt_map.items():
            glyph_name = cmap.get(ord(char))
            new_glyph_name = cmap.get(ord(new_char))
            if glyph_name and new_glyph_name:
                glyph_table[glyph_name] = temp_table[new_glyph_name]
        return decrypt_font

    def distortGlyphs(self, font: TTFont, charSet: Union[Iterable[str],None] = None, noise=1, frequency=0.2):
        '''为字形添加轻微扰动'''
        font = copy.deepcopy(font)
        glyph_set = font.getGlyphSet()
        if (glyph_table := getattr(glyph_set, 'glyfTable', None)):
            def _add_noise_glyf(g: Glyph, table):
                if not g.isComposite():
                    coordinates, end_pts, flags = g.getCoordinates(table)
                    num_points = len(coordinates)
                    num_affected = max(1, int(num_points * frequency)) if num_points else 0
                    affected_indices = random.sample(range(num_points), num_affected)
                    for i in affected_indices:
                        dx = random.randint(-noise, noise)
                        dy = random.randint(-noise, noise)
                        coordinates[i] = (coordinates[i][0] + dx, coordinates[i][1] + dy)
            add_noise = _add_noise_glyf
        elif(glyph_table := getattr(glyph_set, 'charStrings', None)):
            def _add_noise_cff(s: T2CharString, table):
                commands = programToCommands(s.program)
                indices = [
                    index for index, (command, params) in enumerate(commands)
                    if command in ["rmoveto", "hmoveto", "vmoveto", "vlineto","hlineto"]
                ]
                num_affected = max(1, int(len(indices) * frequency)) if indices else 0
                indices_affected = random.sample(indices, num_affected)
                for i in indices_affected:
                    _, args = commands[i]
                    if args:
                        args[random.randint(0, len(args) - 1)] += random.randint(-noise, noise)
                s.setProgram(commandsToProgram(commands))
            add_noise = _add_noise_cff
        else:
            raise ValueError("字体中不存在有效字形表")
        
        if charSet is None:
            for glyph_name in font.getGlyphOrder():
                add_noise(glyph_table[glyph_name], glyph_table)
        else:
            cmap = font.getBestCmap()
            for char in set(charSet):
                glyph_name = cmap.get(ord(char))
                add_noise(glyph_table[glyph_name], glyph_table)
        return font


def main():
    base_path = os.path.abspath(sys.argv[0])
    base_dir = os.path.dirname(base_path)

    skip_char_path = os.path.join(base_dir, "traditional_simplified_charset.txt")

    parser = argparse.ArgumentParser(description="Font and text encryption tool.")
    parser.add_argument("-e", "--encrypt", action="store_true", help="Encryption mode (Default)")
    parser.add_argument("-d", "--decrypt", action="store_true", help="Decryption mode")
    parser.add_argument("-f", "--file", required=True, help="Path to the input text file")
    parser.add_argument("-s", "--save", required=True, help="Path to the output text file")
    parser.add_argument("-fi", "--font-input", required=True, help="Path to the input font file")
    parser.add_argument("-fo", "--font-output", help="Path to the output decryption woff font file in ENCRYPTION")
    parser.add_argument("-savemap", "--save-char-map", help="Path to the output char map json in ENCRYPTION")
    parser.add_argument("-seed", "--seed", help="A random seed for generation of char map in ENCRYPTION")
    parser.add_argument("-map", "--char-map", help="Path to a char map json that will be used in ENCRYPTION or DECRYPTION")
    parser.add_argument("-n", "--noise", action="store_true", help="Whether add noise for glyph distortion in the output font")
    args = parser.parse_args()

    def write_text(file_path: str, text: str):
        Path(file_path).write_text(text, encoding="utf-8")
    def read_text(file_path: str):
        return Path(file_path).read_text(encoding="utf-8")

    if args.decrypt:
        if not args.char_map:
            raise ValueError("Decryption mode needs a char map, use `-m` to specify one")
        text = read_text(args.file)
        encryptor = FontEncryptor(args.font_input, skip_str=read_text(skip_char_path))
        char_map = json.loads(read_text(args.char_map))
        decrypted_text = encryptor.decrypt_text(text, char_map)
        write_text(args.save, decrypted_text)
    else:
        text = read_text(args.file)
        encryptor = FontEncryptor(args.font_input, skip_str=read_text(skip_char_path), seed=args.seed if args.seed else 42)

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

        # 生成解密字体，如果以b64结尾，则直接生成其 woff 格式的 base64 文本
        if args.font_output:
            decrypt_font = encryptor.generate_decrypt_font(trimmed_font, char_map)

            # 为字体添加扰动，默认为大小1，频率0.2的扰动
            if args.noise:
                decrypt_font = encryptor.distortGlyphs(decrypt_font, char_map.values(), noise=1, frequency=0.2)

            if(args.font_output.endswith('.b64')):
                decrypt_font.flavor = 'woff'
                buffer = io.BytesIO()
                decrypt_font.save(buffer)
                buffer.seek(0)
                base64_str = base64.b64encode(buffer.read()).decode("utf-8")
                write_text(args.font_output, base64_str)
            elif(args.font_output.endswith('.ttx')):
                decrypt_font.saveXML(args.font_output)
            else:
                if(args.font_output.endswith('.woff')):
                    decrypt_font.flavor = 'woff'
                elif(args.font_output.endswith('.woff2')):
                    decrypt_font.flavor = 'woff2'
                else:
                    decrypt_font.flavor = None
                decrypt_font.save(args.font_output)

if __name__ == "__main__":
    main()
