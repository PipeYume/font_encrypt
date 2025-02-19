import argparse
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.subset import Subsetter, Options, load_font, save_font
from fontTools.misc.psCharStrings import T2CharString
from fontTools.cffLib.specializer import programToCommands, commandsToProgram
from pathlib import Path
from typing import Optional, Set, Dict, Union, Iterable
import re
import random
import json
import os, sys, io, base64
import fastrand
# from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
# from fontTools.cffLib import CharStrings

PathLike = Union[str, os.PathLike]

class FontEncryptor:
    pattern: re.Pattern
    '''正则匹配需要加密的字'''
    skip_char_set: Set[str]
    '''跳过不需要加密的字'''
    seed: int

    def __init__(self, pattern: Optional[str]=r'[\u4e00-\u9fff]', skip_str: str="", seed: int=42):
        if pattern:
            self.pattern = re.compile(pattern)
        else:
            self.pattern = re.compile(r"[\s\S]")

        if skip_str:
            self.skip_char_set = self.get_valid_char_set(skip_str)
        else:
            self.skip_char_set = set()

        random.seed(seed)
        
        # 创建 Subsetter 对象
        options = Options()
        options.ignore_missing_glyphs = True  # 忽略缺少的字符
        self.subsetter = Subsetter(options=options)
        pass

    def get_valid_char_set(self,text: str):
        char_set = set(self.pattern.findall(text))
        return char_set

    def get_trimmed_font(self,font_path: PathLike, text: str, fontNumber=0):
        font = load_font(font_path, Options(font_number=fontNumber))
        self.subsetter.populate(text=text)
        self.subsetter.subset(font)
        return font

    def generate_char_map(self, text: str, font: Optional[TTFont]=None):
        char_set = self.get_valid_char_set(text) - self.skip_char_set
        # 排除字体中没有的字
        if font:
            cmap = font.getBestCmap()
            noexists_set = [char for char in char_set if not cmap.get(ord(char))]
            char_set = sorted(char_set - set(noexists_set))
        # 生成随机映射
        shuffled_chars = list(char_set)
        random.shuffle(shuffled_chars)
        char_map:dict[str, str] = dict(zip(char_set, shuffled_chars))
        return char_map

    def encrypt_text(self, text: str, char_map: Dict[str, str]):
        translation_table = str.maketrans(char_map)
        return text.translate(translation_table)

    def decrypt_text(self, text: str, char_map: Dict[str, str]):
        decrypt_map = {v: k for k, v in char_map.items()}
        translation_table = str.maketrans(decrypt_map)
        return text.translate(translation_table)

    def convert_to_decrypt_font(self, font: TTFont, char_map: Dict[str, str]):
        decrypt_map = {v: k for k, v in char_map.items()}
        # 获取 cmap 表
        cmap = font.getBestCmap()
        glyph_set = font.getGlyphSet()
        # 统一处理字形表
        if table := getattr(glyph_set, 'glyfTable', None):
            glyf = True
        elif table := getattr(glyph_set, 'charStrings', None):
            glyf = False
        else:
            raise ValueError("字体中不存在有效字形表")

        # 交换字形
        # 对于TTF字体，这里访问 table__g_l_y_f 类型的元素要用 .glyphs 来访问
        # 直接使用 glyph_table[galyph_name] 会导致额外执行 glyph.expand, 有巨额时间开销
        glyph_cache = {}
        table = table.glyphs if glyf else table
        for name in table.keys():
            glyph_cache[name] = table[name]

        for char, new_char in decrypt_map.items():
            glyph_name = cmap.get(ord(char))
            new_glyph_name = cmap.get(ord(new_char))
            if glyph_name is None or new_glyph_name is None:
                continue
            table[glyph_name] = glyph_cache[new_glyph_name]

    def _add_noise_glyf(self, g: Glyph, table, frequency, noise):
        '''为 glyf 字形添加扰动'''
        if not g.isComposite():
            coordinates, end_pts, flags = g.getCoordinates(table)
            num_points = len(coordinates)
            num_affected = max(1, int(num_points * frequency)) if num_points else 0
            # Generate random unique indices
            affected_indices = set()
            max_attempts = num_points * 2
            while len(affected_indices) < num_affected:
                if len(affected_indices) >= num_points:
                    break
                index = fastrand.pcg32bounded(num_points)
                affected_indices.add(index)
                if max_attempts <= 0:
                    break
                max_attempts -= 1

            for i in affected_indices:
                dx = fastrand.pcg32bounded(2*noise+1)-noise
                dy = fastrand.pcg32bounded(2*noise+1)-noise
                x, y = coordinates[i]
                coordinates[i] = (x + dx, y + dy)

    def _add_noise_cff(self, s: T2CharString, table, frequency, noise):
        '''为 CFF 字形添加扰动'''
        commands = programToCommands(s.program)
        indices = [
            index for index, (command, params) in enumerate(commands)
            if command in ["rmoveto", "hmoveto", "vmoveto", "vlineto", "hlineto"]
        ]
        num_affected = max(1, int(len(indices) * frequency)) if indices else 0
        indices_affected = random.sample(indices, num_affected)
        for i in indices_affected:
            _, args = commands[i]
            if args:
                args[fastrand.pcg32bounded(len(args))] += fastrand.pcg32bounded(2*noise+1)-noise
        s.setProgram(commandsToProgram(commands))

    def distortFont(self, font: TTFont, charSet: Union[Iterable[str],None] = None, noise=1, frequency=0.2):
        '''为字形添加轻微扰动'''
        glyph_set = font.getGlyphSet()
        if (glyph_table := getattr(glyph_set, 'glyfTable', None)):
            add_noise = self._add_noise_glyf
        elif(glyph_table := getattr(glyph_set, 'charStrings', None)):
            add_noise = self._add_noise_cff
        else:
            raise ValueError("字体中不存在有效字形表")
        
        if charSet is None:
            order = font.getGlyphOrder()
            for glyph_name in order:
                add_noise(glyph_table[glyph_name], glyph_table, frequency, noise)
        else:
            cmap = font.getBestCmap()
            for char in set(charSet):
                if glyph_name := cmap.get(ord(char)):
                    add_noise(glyph_table[glyph_name], glyph_table, frequency, noise)

def main():
    base_path = os.path.abspath(sys.argv[0])
    base_dir = os.path.dirname(base_path)


    def write_text(file_path: str, text: str):
        Path(file_path).write_text(text, encoding="utf-8")
    def read_text(file_path: str):
        return Path(file_path).read_text(encoding="utf-8")
    
    skip_char_path = os.path.join(base_dir, "traditional_simplified_charset.txt")
    traditional_simplified_charset = read_text(skip_char_path)

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

    if args.decrypt:
        if not args.char_map:
            raise ValueError("Decryption mode needs a char map, use `-m` to specify one")
        text = read_text(args.file)
        encryptor = FontEncryptor(args.font_input, skip_str=traditional_simplified_charset)
        char_map = json.loads(read_text(args.char_map))
        decrypted_text = encryptor.decrypt_text(text, char_map)
        write_text(args.save, decrypted_text)
    else:
        text = read_text(args.file)
        encryptor = FontEncryptor(skip_str=traditional_simplified_charset, seed=args.seed if args.seed else fastrand.pcg32bounded(1000000))

        # 裁剪字体，考虑字体的繁简转换，文章的繁简版本全部都要保留
        text_set = set(text)
        add_set = set()
        simplified_chars = traditional_simplified_charset.split("\n")[0]
        traditional_chars = traditional_simplified_charset.split("\n")[1]
        # 这里不能用字典，因为一个简体/繁体字 可能对应 多个繁体/简体字
        for c, t in zip(simplified_chars, traditional_chars):
            if c in text_set:
                add_set.add(t)
            if t in text_set:
                add_set.add(c)
        trimmed_font = encryptor.get_trimmed_font(args.font_input,''.join(text_set.union(add_set)))

        # 生成char map
        if args.char_map:
            char_map = json.loads(read_text(args.char_map))
        else:
            char_map = encryptor.generate_char_map(text, trimmed_font)
        if(args.save_char_map):
            write_text(args.save_char_map, json.dumps(char_map,ensure_ascii=False, indent=4))
        
        # 生成加密文字
        encrypted_text = encryptor.encrypt_text(text, char_map)
        write_text(args.save, encrypted_text)

        # 生成解密字体，如果以b64结尾，则直接生成其 woff 格式的 base64 文本
        if args.font_output:
            encryptor.convert_to_decrypt_font(trimmed_font, char_map)
            decrypt_font = trimmed_font

            # 为字体添加扰动，默认为大小1，频率0.2的扰动
            if args.noise:
                encryptor.distortFont(decrypt_font, char_map.values(), noise=1, frequency=0.2)

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
                    flavor = 'woff'
                elif(args.font_output.endswith('.woff2')):
                    flavor = 'woff2'
                else:
                    flavor = None
                save_font(decrypt_font,outfile=args.font_output,options=Options(flavor=flavor))

if __name__ == "__main__":
    main()
