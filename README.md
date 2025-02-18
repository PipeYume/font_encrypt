# FontEncryptor

## 简介

`FontEncryptor` 是一个基于 Python 的字体和文本加密工具。它可以通过子集化字体文件并对文本进行字符映射加密，以实现文本保护和可逆转换。

本项目使用python 3.8.19 开发，不过后续版本兼容性应该有的（大概）。

## 功能

- **文本加密**：对文本内容进行字符替换加密，生成不可读但可逆的密文。
- **文本解密**：使用已保存的字符映射表，将密文还原为原始文本。
- **字体子集化**：生成只包含加密字符的精简字体。
- **加密字体生成**：创建用于解密字体文件，以便在 Web 端使用。

## 依赖项

请确保您的环境已安装以下 Python 依赖项：

```bash
pip install fonttools
```

## 直接使用 encryptor.py 的注意事项

1. 生成的字体文件若指定的路径后缀为`.b64`，则生成的是其 `woff` 格式的 base64 编码。
2. 加密的字符是 所有汉字：`pattern=r'[\u4e00-\u9fff]'`，跳过加密的字符为 `traditional_simplified_charset.txt` 中的字符（繁简转换影响的字符），因为一些网站具有繁简切换功能，加密这些字符的话，在切换繁简后无法正确解密。

## 使用方法

### 1. 运行加密模式

```bash
python encryptor.py -f input.txt -s encrypt.txt -fi SourceHanMonoSC-Regular.otf -fo decrypt.woff -savemap char_map.json
```

**参数说明：**

- `-e, --encrypt`：加密模式（默认，可以不写）
- `-f, --file`：输入文本文件
- `-s, --save`：加密后的输出文本文件
- `-savemap, --save-char-map`：输出字符映射 JSON 文件
- `-fi, --font-input`：输入字体文件
- `-fo, --font-output`：生成解密用字体文件，`.b64`后缀时是woff格式字体的base64编码。
- `--seed`：影响char_map生成的随机数种子
- `-map, --char-map`：用于加密的字符映射 JSON 文件（使用时，不会生成新的char_map）

#### 使用自定义字符映射加密

如果想使用已有的字符映射进行加密，可通过 `-map` 指定 JSON 文件。

```bash
python encryptor.py -f input.txt -s encrypt.txt -fi SourceHanMonoSC-Regular.otf -fo decrypt.woff -map char_map.json
```

### 2. 运行解密模式

```bash
python encryptor.py -d -f encrypt.txt -s decrypt.txt -map char_map.json
```

**参数说明：**

- `-d, --decrypt`：解密模式
- `-f, --file`：输入的加密文本文件
- `-s, --save`：解密后的输出文本文件
- `-map, --char-map`：用于解密的字符映射 JSON 文件。在解密模式下是必须的。

## 示例

### 输入

```text
你好，世界！
```

### 加密后

```text
好世，界你！
```

### 字符映射 (`char_map`)

```json
{
    "你": "好",
    "好": "世",
    "世": "界",
    "界": "你"
}
```

### 解密后（使用解密字体查看 或者 使用解密模式解密）

```text
你好，世界！
```

## 你也可以手动使用 `FontEncryptor` 来实现更个性化的加解密

### 初始化参数

```python
FontEncryptor(
    font_path: PathLike,  # 字体文件路径
    pattern: Optional[str] = r'[\u4e00-\u9fff]',  # 正则匹配需要加密的字
    skip_str: str = "",  # 跳过不需要加密的字
    seed: int = 42  # 随机种子，影响char_map
)
```

### 标准加密流程

```python
from encryptor import FontEncryptor
from pathlib import Path

# 读取文本文件
text = Path("input.txt").read_text(encoding="utf-8")

# 初始化 FontEncryptor
encryptor = FontEncryptor("SourceHanMonoSC-Regular.otf", skip_str="跳过的字符", seed=42)

# 裁剪字体
trimmed_font = encryptor.trim_font(text)

# 生成字符映射
char_map = encryptor.generate_char_map(text)

# 生成加密文字
encrypted_text = encryptor.encrypt_text(text, char_map)

# 生成解密字体
decrypt_font = encryptor.generate_decrypt_font(trimmed_font, char_map)

decrypt_font.save("decrypt.woff")

# 解密文本
decrypted_text = encryptor.decrypt_text(encrypted_text, char_map)

print("加密后:", encrypted_text)
print("解密后:", decrypted_text)
```

## 许可证

本工具遵循 MIT 许可证，欢迎自由使用和修改。
