# FontEncryptor

## 简介

`FontEncryptor` 是一个基于 Python 的字体和文本加密工具。它可以通过子集化字体文件并对文本进行字符映射加密，以实现文本保护和可逆转换。

本项目使用python 3.8.19 开发，不过后续版本兼容性应该有的（大概）。

## 功能

- **文本加密**：对文本内容进行字符替换加密，生成不可读但可逆的密文。
- **文本解密**：使用已保存的字符映射表，将密文还原为原始文本。
- **字体子集化**：生成只包含加密字符的精简字体。
- **加密字体生成**：创建用于解密的 `.woff` 字体文件，以便在 Web 端使用。如需创建其它类型的字体，请将代码中的以下部分注释掉

```python
if(not args.woff.endswith(".woff")):
    raise ValueError("The output woff font path must be ended with .woff")
```

## 依赖项

请确保您的环境已安装以下 Python 依赖项：

```bash
pip install fonttools
```

## 使用方法

### 1. 运行加密模式

```bash
python encryptor.py -e -f input.txt -s encrypted.txt -savemap char_map.json -t decrypt_font.woff
```

**参数说明：**

- `-e, --encrypt`：加密模式（默认，可以不写）
- `-f, --file`：输入文本文件
- `-s, --save`：加密后的输出文本文件
- `-savemap, --save-char-map`：输出字符映射 JSON 文件
- `-t, --woff`：生成解密用 `.woff` 字体文件
- `--seed`：生成char_map的随机数种子
- `-map, --char-map`：用于加密的字符映射 JSON 文件（使用时，不会生成新的char_map）

### 2. 运行解密模式

```bash
python encryptor.py -d -f encrypted.txt -s decrypted.txt -map char_map.json
```

**参数说明：**

- `-d, --decrypt`：解密模式
- `-f, --file`：输入的加密文本文件
- `-s, --save`：解密后的输出文本文件
- `-map, --char-map`：用于解密的字符映射 JSON 文件

### 3. 使用自定义字符映射

如果想使用已有的字符映射进行加密或解密，可通过 `-map` 指定 JSON 文件。

```bash
python encryptor.py -e -f input.txt -s encrypted.txt -map char_map.json
```

## 示例

### 输入

```text
你好，世界！
```

### 加密后

```text
佗伋，佖佗！
```

### 字符映射 (`char_map`)

```json
{
    "你": "佗",
    "好": "伋",
    "世": "佖",
    "界": "佗"
}
```

### 解密后（使用解密字体查看 或者 使用解密模式解密）

```text
你好，世界！
```

## 注意事项

1. 字体文件路径默认为 `msyh.ttc`，可根据需要修改。
2. 加密和解密必须使用相同的字符映射表 (`char_map.json`)。
3. 生成的 `.woff` 字体适用于 Web 端的加密文字显示和解密。

## 许可证

本工具遵循 MIT 许可证，欢迎自由使用和修改。
