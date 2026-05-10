# -*- coding: utf-8 -*-

# 导入所需的库
import sys
from enum import Enum
import time
import os
import platform
import traceback
from threading import Thread
from pathlib import Path
from signal import signal, SIGINT, SIG_IGN
from subprocess import run
from shutil import rmtree

sys.stdout.reconfigure(encoding='utf-8')
os.environ["PYTHONUTF8"] = "1"
if "" in sys.path:
    sys.path.insert(0, sys.path.pop(sys.path.index("")))

# 尝试导入第三方库，若未安装则提示用户
try:
    from keyboard import add_hotkey
except ImportError:
    print("找不到库：keyboard", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True  # 标记tqdm库是否可用
except ImportError:
    TQDM_AVAILABLE = False    # 轻量级进度条替代类（当tqdm未安装时使用）
    from .utils.tqdm import tqdm

try:
    from loguru import logger as log
except ImportError:
    from .utils.loguru import logger as log

# ==================== ANSI 颜色常量 ====================
class Style:
    # 基础前景色（文字颜色）
    RED = "\033[31m"     # 红色
    GREEN = "\033[32m"   # 绿色
    YELLOW = "\033[33m"  # 黄色
    BLUE = "\033[34m"    # 蓝色
    MAGENTA = "\033[35m" # 品红
    CYAN = "\033[36m"    # 青色
    WHITE = "\033[37m"   # 白色
    
    
    # 亮色前景色（更鲜艳的颜色）
    BRIGHT_RED = "\033[91m"    # 亮红
    BRIGHT_GREEN = "\033[92m"  # 亮绿
    BRIGHT_YELLOW = "\033[93m" # 亮黄
    BRIGHT_BLUE = "\033[94m"   # 亮蓝
    BRIGHT_CYAN = "\033[96m"   # 亮青
    
    # 文字样式
    BOLD = "\033[1m"      # 加粗
    UNDERLINE = "\033[4m" # 下划线
    
    # 重置颜色和样式（避免影响后续输出）
    RESET = "\033[0m"

# 获取时间
date = time.localtime()
year = date.tm_year
month = date.tm_mon
day = date.tm_mday

# ==================== 配置类（存储程序所有配置项）====================
class ToolConfig:
    VERSION = "10.9.2-beta"           # 软件版本号
    AUTHOR = "杨锦轩"                  # 作者名称
    AGE = (year - 2016 - 1            # 作者年龄
        if month != 11
        else (year - 2016 - 1 
            if day < 22 
            else year - 2016
        )
    )
    MAX_HISTORY_COUNT = 200           # 最大历史记录数
    ARROW_RIGHT = "→"                 # 统一为普通箭头
    SYSTEM_TYPE = platform.system()   # 操作系统类型（Windows/Linux/Mac/Android）
    IS_MOBILE = "Android" in SYSTEM_TYPE or "termux" in sys.prefix.lower()  # 是否为移动设备
    IS_WINDOWS = SYSTEM_TYPE == "Windows"  # 是否为Windows系统
    IS_PC = not IS_MOBILE # 是否为电脑
    
    # 历史文件路径（纯文本.txt格式）- 优化路径选择（确保不同系统都能正常写入）
    @property
    def HISTORY_FILE(self) -> Path:
        # 使用当前目录
        return Path(os.getcwd()) / "src" / "assets" / "history" / "codeconv_history.txt"
    # 支持的编码模式
    SUPPORTED_MODES = ["Windows1252", "ASCII"]
    # 默认编码模式
    converter_mode = "Windows1252"
    # 支持的字符串转字节模式
    SUPPORTED_DECODE_BYTES_MODES = ["utf-8", "utf-16", "utf-16le", "utf-16be", "utf-32", "utf-32le", "utf-32be"]
    # 支持的字节转字符串模式
    SUPPORTED_ENCODE_BYTES_MODES = ["ascii", "cp1252"]
    # 动态属性：返回当前模式对应的编码参数（根据模式自动切换）
    @property
    def start_file_encoding(self) -> str:
        """当前模式对应的文件打开编码（读取文件时使用）"""
        return "cp1252" if self.converter_mode == "Windows1252" else "ascii"
    
    @property
    def code_range(self) -> tuple[int, int]:
        """当前模式的有效编码范围：ASCII(0-127)，Windows1252(0-255)"""
        if self.converter_mode == "ASCII":
            return (0, 127)
        else:
            return (0, 255)
    
    @property
    def CODE_MIN(self) -> int:
        """当前模式的最小有效编码值（动态获取，与模式同步）"""
        return self.code_range[0]
    
    @property
    def CODE_MAX(self) -> int:
        """当前模式的最大有效编码值（动态获取，与模式同步）"""
        return self.code_range[1]
    
    # 命令集（命令名：命令描述，快捷键）
    COMMANDS: dict[str, str] = {
        "历史记录": f"查看操作历史记录{'按Ctrl+H' if IS_PC else ''} 📜",
        "清空历史": f"清空所有历史记录{'按F1' if IS_PC else ''} 🗑️",
        "编码": f"切换到编码模式（字符→编码）{'按Ctrl+E' if IS_PC else ''} 🔤→🔢",
        "解码": f"切换到解码模式（编码→字符）{'按Ctrl+D' if IS_PC else ''} 🔢→🔤",
        "批量处理": f"批量文件处理（支持多行为输入）{'按F2' if IS_PC else ''}📁",
        "字符串转换": f"字符串转换模式（整段文字/编码批量转换）{'按F3' if IS_PC else ''} 📝",
        "验证编码": f"验证文件编码兼容性（检查文件是否符合当前模式）{'按F4' if IS_PC else ''} ✅",
        "系统配置": f"查看系统配置信息（版本、编码模式、路径等）{'按Alt+C' if IS_PC else ''}⚙️",
        "帮助": f"显示命令帮助文档（所有命令的详细说明）{'按F5' if IS_PC else ''} ❓",
        "版本信息": f"显示软件版本信息（含Python版本、系统类型）{'按Alt+V' if IS_PC else ''} 📌",
        "退出": f"退出程序 🚪{'按Ctrl+Q' if IS_PC else ''}",
        "所有命令": f"显示所有可用命令（简洁列表）{'按F6' if IS_PC else ''} 📋",
        "切换Windows1252": f"切换到Windows-1252模式（编码范围0-255，支持更多字符）{'按Ctrl+W' if IS_PC else ''} 🌐",
        "切换ASCII": f"切换到ASCII模式（编码范围0-127，标准ASCII字符集）{'按Ctrl+A' if IS_PC else ''} 📟",
        "清空输出": f"清空所有输出内容（清屏，不影响历史记录）{'按F7' if IS_PC else ''} 🧹",
        "作者信息": f"输出作者的信息{'按F8' if IS_PC else ''} 🧑",
        "转换成字节": f"将字符串以指定编码转换成字节{'按Ctrl+B' if IS_PC else ''}",
        "转换成字符串": f"将字节已指定的编码转换成字符串{'按Alt+B' if IS_PC else ''}",
        "日志": "显示日志 📃",
        "删除日志": "将日志删除 📃"
    }
    
    # 控制字符枚举（ASCII和Windows-1252共用：0-31 + 127）- 用于显示控制字符的中文名称
    class CONTROL_CHAR_NAMES(Enum):
        NUL = 0       # 空字符
        SOH = 1       # 标题开始
        STX = 2       # 文本开始
        ETX = 3       # 文本结束
        EOT = 4       # 传输结束
        ENQ = 5       # 询问
        ACK = 6       # 确认
        BEL = 7       # 响铃
        BS = 8        # 退格
        HT = 9        # 水平制表符
        LF = 10       # 换行
        VT = 11       # 垂直制表符
        FF = 12       # 换页
        CR = 13       # 回车
        SO = 14       # 移出
        SI = 15       # 移入
        DLE = 16      # 数据链路转义
        DC1 = 17      # 设备控制1
        DC2 = 18      # 设备控制2
        DC3 = 19      # 设备控制3
        DC4 = 20      # 设备控制4
        NAK = 21      # 否定确认
        SYN = 22      # 同步空闲
        ETB = 23      # 传输块结束
        CAN = 24      # 取消
        EM = 25       # 媒体结束
        SUB = 26      # 替换
        ESC = 27      # 转义
        FS = 28       # 文件分隔符
        GS = 29       # 组分隔符
        RS = 30       # 记录分隔符
        US = 31       # 单元分隔符
        DEL = 127     # 删除

    # Windows-1252字符映射表（完整保留128-255范围，含特殊字符）
    WINDOWS1252_CHAR_MAP: dict[int, str] = {
        128: '\u20AC', 129: "[未分配]", 130: '\u201A', 131: '\u0192', 132: '\u201E', 133: '\u2026',
        134: '\u2020', 135: '\u2021', 136: '\u02C6', 137: '\u2030', 138: '\u0160', 139: '\u2039',
        140: '\u0152', 141: "[未分配]", 142: '\u017D', 143: "[未分配]", 144: "[未分配]",
        145: '\u2018', 146: '\u2019', 147: '\u201C', 148: '\u201D', 149: '\u2022', 150: '\u2013',
        151: '\u2014', 152: '\u02DC', 153: '\u2122', 154: '\u0161', 155: '\u203A', 156: '\u0153',
        157: "[未分配]", 158: '\u017E', 159: '\u0178', 160: '\u00A0', 161: '\u00A1', 162: '\u00A2',
        163: '\u00A3', 164: '\u00A4', 165: '\u00A5', 166: '\u00A6', 167: '\u00A7', 168: '\u00A8',
        169: '\u00A9', 170: '\u00AA', 171: '\u00AB', 172: '\u00AC', 173: '\u00AD', 174: '\u00AE',
        175: '\u00AF', 176: '\u00B0', 177: '\u00B1', 178: '\u00B2', 179: '\u00B3', 180: '\u00B4',
        181: '\u00B5', 182: '\u00B6', 183: '\u00B7', 184: '\u00B8', 185: '\u00B9', 186: '\u00BA',
        187: '\u00BB', 188: '\u00BC', 189: '\u00BD', 190: '\u00BE', 191: '\u00BF', 192: '\u00C0',
        193: '\u00C1', 194: '\u00C2', 195: '\u00C3', 196: '\u00C4', 197: '\u00C5', 198: '\u00C6',
        199: '\u00C7', 200: '\u00C8', 201: '\u00C9', 202: '\u00CA', 203: '\u00CB', 204: '\u00CC',
        205: '\u00CD', 206: '\u00CE', 207: '\u00CF', 208: '\u00D0', 209: '\u00D1', 210: '\u00D2',
        211: '\u00D3', 212: '\u00D4', 213: '\u00D5', 214: '\u00D6', 215: '\u00D7', 216: '\u00D8',
        217: '\u00D9', 218: '\u00DA', 219: '\u00DB', 220: '\u00DC', 221: '\u00DD', 222: '\u00DE',
        223: '\u00DF', 224: '\u00E0', 225: '\u00E1', 226: '\u00E2', 227: '\u00E3', 228: '\u00E4',
        229: '\u00E5', 230: '\u00E6', 231: '\u00E7', 232: '\u00E8', 233: '\u00E9', 234: '\u00EA',
        235: '\u00EB', 236: '\u00EC', 237: '\u00ED', 238: '\u00EE', 239: '\u00EF', 240: '\u00F0',
        241: '\u00F1', 242: '\u00F2', 243: '\u00F3', 244: '\u00F4', 245: '\u00F5', 246: '\u00F6',
        247: '\u00F7', 248: '\u00F8', 249: '\u00F9', 250: '\u00FA', 251: '\u00FB', 252: '\u00FC',
        253: '\u00FD', 254: '\u00FE', 255: '\u00FF'
    }
    
    # 快捷键集（快捷键: 功能）
    HOTKEYS: dict[str, str] = {
        "ctrl+h": "历史记录",
        "f1": "清空历史",
        "ctrl+e": "编码",
        "ctrl+d": "解码",
        "f2": "批量处理",
        "f3": "字符串转换",
        "f4": "验证编码",
        "alt+c": "系统配置",
        "f5": "帮助",
        "alt+v": "版本信息",
        "ctrl+q": "退出",
        "f6": "所有命令",
        "ctrl+w": "切换Windows1252",
        "f7": "切换ASCII",
        "f8": "作者信息",
        "ctrl+b": "转换成字节",
        "alt+b": "转换成字符串"
    }

    # 反向映射（用于编码模式：字符→编码）- 按当前模式动态生成
    @property
    def CHAR_TO_CODE(self) -> dict[str, int]:
        """当前模式的字符到编码的映射表（编码模式使用）"""
        if self.converter_mode == "Windows1252":
            return {v: k for k, v in self.WINDOWS1252_CHAR_MAP.items() if v != "[未分配]"}
        else:
            return {chr(code): code for code in range(0, 128)}
    
    # 控制字符集合（共用）- 用于快速判断是否为控制字符
    CONTROL_VALUE_SET = set(CONTROL_CHAR_NAMES._value2member_map_.keys())
    CONTROL_NAME_SET = set(CONTROL_CHAR_NAMES._member_names_)

# 创建配置实例（全局唯一，所有模块共享）
config = ToolConfig()

# 为Windows系统启用ANSI颜色支持（默认不支持，需手动开启）
if config.IS_WINDOWS:
    run("reg add HKCU\\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1", shell=True)
    run("color", shell=True)

# 全局变量：存储快捷键触发的命令（初始为空）
hotkey_cmd = ""

# ------------------------------
# 初始化
# ------------------------------
def init():
    # ------------------------------
    # 快捷键功能
    # ------------------------------
    def on_hotkey_press(cmd):
        """快捷键回调：只把命令存到全局变量，不处理逻辑"""
        global hotkey_cmd
        hotkey_cmd = cmd

    # 注册所有快捷键
    for hotkey, cmd in config.HOTKEYS.items():
        add_hotkey(hotkey, on_hotkey_press, args=(cmd,))

    init_history_file()
    init_log()


# 屏蔽Ctrl+C退出
def ignore_ctrl_c():
    signal(SIGINT, SIG_IGN)
    print(f"{Style.YELLOW}⚠️ 警告：Ctrl+C已屏蔽！{Style.RESET}")

# ------------------------------
# 初始化日志
# ------------------------------
def init_log():
    log_dir = Path(os.getcwd()) / "src" / "assets" / "log"
    log_file_name = f"codeconv-{year}/{month}/{day}.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    log.remove()

    log.add(
        sink=log_dir / log_file_name,
        format="[{time:YYYY/MM/DD HH:mm:ss.SSSSSS}] - [{level}] - {message}",
        encoding="utf-8",
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        compression="zip",
        enqueue=True,
        diagnose=True
    )


# ------------------------------
# 纯文本历史记录存储功能（读写历史操作记录）
# ------------------------------
def init_history_file():
    """初始化历史文件 - 若父目录或文件不存在则创建，确保文件可写入"""
    try:
        history_parent = config.HISTORY_FILE.parent
        history_parent.mkdir(parents=True, exist_ok=True)
        
        if not config.IS_WINDOWS:
            os.chmod(history_parent, 0o755)
        
        if not config.HISTORY_FILE.exists():
            with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
            
            if not config.IS_WINDOWS:
                os.chmod(config.HISTORY_FILE, 0o644)
                
            print(f"{Style.GREEN}历史文件已初始化 📜{Style.RESET}")
    except Exception as e:
        print(f"{Style.YELLOW}警告：初始化历史文件失败 ⚠️ - {e}{Style.RESET}")

def save_history(input_value: str, output_value: str, mode: str):
    """保存操作历史到纯文本文件（自动限制最大记录数）"""
    try:
        init_history_file()
        
        history_file = config.HISTORY_FILE
        if not os.access(history_file.parent, os.W_OK) or (history_file.exists() and not os.access(history_file, os.W_OK)):
            history_file = Path(os.getcwd()) / "ascii转换器_历史记录_备用.txt"
        
        history = read_history(history_file)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        record = f"[{timestamp}] [{mode.upper()}] {input_value} {config.ARROW_RIGHT} {output_value}\n"
        
        history.append(record)
        if len(history) > config.MAX_HISTORY_COUNT:
            history = history[-config.MAX_HISTORY_COUNT:]
        
        with open(history_file, "w", encoding="utf-8", errors="replace") as f:
            f.writelines(history)
            
    except PermissionError:
        print(f"{Style.RED}错误：权限不足，无法写入历史文件 🚫{Style.RESET}")
    except Exception as e:
        print(f"{Style.RED}错误：保存历史记录失败 ❌ - {e}{Style.RESET}")

def read_history(custom_path: Path | None = None) -> list[str]:
    """从纯文本文件读取历史记录（自动兼容备用路径）"""
    try:
        history_file = custom_path or config.HISTORY_FILE
        
        if not history_file.exists():
            fallback_path = Path(os.getcwd()) / "ascii转换器_历史记录_备用.txt"
            if fallback_path.exists():
                history_file = fallback_path
            else:
                return []
        
        with open(history_file, "r", encoding="utf-8", errors="replace") as f:
            return [line.strip() for line in f if line.strip()]
    except PermissionError:
        print(f"{Style.RED}错误：权限不足，无法读取历史文件 🚫{Style.RESET}")
        return []
    except Exception as e:
        print(f"{Style.RED}错误：读取历史记录失败 ❌ - {e}{Style.RESET}")
        return []

def clear_history():
    """清空历史文件中的所有记录"""
    try:
        init_history_file()
        
        history_file = config.HISTORY_FILE
        if not os.access(history_file.parent, os.W_OK) or (history_file.exists() and not os.access(history_file, os.W_OK)):
            history_file = Path(os.getcwd()) / "ascii转换器_历史记录_备用.txt"
        
        with open(history_file, "w", encoding="utf-8") as f:
            f.write("")
        print(f"{Style.GREEN}历史记录已清空 🗑️{Style.RESET}")
    except PermissionError:
        print(f"{Style.RED}错误：权限不足，无法清空历史文件 🚫{Style.RESET}")
    except Exception as e:
        print(f"{Style.RED}错误：清空历史记录失败 ❌ - {e}{Style.RESET}")

# ------------------------------
# 批量处理函数（处理多文件/多行输入）
# ------------------------------
def batch_decode(file_path: str, output_path: str | None = None):
    """批量解码：将文件中的编码值转换为字符（按当前模式处理）"""
    result_lines = [f"=== 批量解码结果（模式：{config.converter_mode}）==="]
    print(f"\n{Style.CYAN}=== 批量解码模式 📥🔢→🔤（当前：{config.converter_mode} - 编码范围{config.CODE_MIN}-{config.CODE_MAX}）==={Style.RESET}")
    
    try:
        with open(file_path, "r", encoding=config.start_file_encoding) as f:
            lines = f.readlines()
        
        progress = tqdm(total=len(lines), desc="解码行", unit="行", ncols=80)
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                progress.update(1)
                continue
            
            try:
                win_code = int(line)
                if not (config.CODE_MIN <= win_code <= config.CODE_MAX):
                    log = f"第{line_num}行：{line} {config.ARROW_RIGHT} 超出编码范围（{config.CODE_MIN}-{config.CODE_MAX}）⚠️"
                    print(f"{Style.YELLOW}{log}{Style.RESET}")
                else:
                    if win_code in config.CONTROL_VALUE_SET:
                        char_name = config.CONTROL_CHAR_NAMES(win_code).name
                        log = f"第{line_num}行：{win_code} {config.ARROW_RIGHT} [控制字符:{char_name}] 🎛️"
                        print(f"{Style.BLUE}{log}{Style.RESET}")
                    else:
                        if config.converter_mode == "Windows1252":
                            display_char = config.WINDOWS1252_CHAR_MAP.get(win_code, chr(win_code))
                        else:
                            display_char = chr(win_code)
                        
                        display_char = display_char if display_char != " " else "[空格] 🚀"
                        log = f"第{line_num}行：{win_code} {config.ARROW_RIGHT} {display_char}"
                        print(f"{Style.WHITE}{log}{Style.RESET}")
                
                result_lines.append(log)
            
            except ValueError:
                log = f"第{line_num}行：{line} {config.ARROW_RIGHT} 无效编码值（不是整数）❌"
                print(f"{Style.RED}{log}{Style.RESET}")
                result_lines.append(log)
            
            progress.update(1)
        
        progress.close()
        
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(result_lines))
            print(f"\n{Style.GREEN}结果已保存到：{output_path} 📥{Style.RESET}")
    
    except FileNotFoundError:
        print(f"{Style.RED}错误：输入文件不存在 ❌{Style.RESET}")
    except PermissionError:
        print(f"{Style.RED}错误：无权限读取输入文件 🚫{Style.RESET}")
    except Exception as e:
        print(f"{Style.RED}错误：批量解码过程失败 ❌ - {e}{Style.RESET}")
        print(traceback.format_exc())

def batch_encode(file_path: str, output_path: str | None = None):
    """批量编码：将文件中的字符/控制字符名称转换为编码值（按当前模式处理）"""
    result_lines = [f"=== 批量编码结果（模式：{config.converter_mode}）==="]
    print(f"\n{Style.CYAN}=== 批量编码模式 📥🔤→🔢（当前：{config.converter_mode} - 编码范围{config.CODE_MIN}-{config.CODE_MAX}）==={Style.RESET}")
    
    try:
        with open(file_path, "r", encoding=config.start_file_encoding) as f:
            lines = f.readlines()
        
        progress = tqdm(total=len(lines), desc="编码行", unit="行", ncols=80)
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                progress.update(1)
                continue
            
            upper_line = line.upper()
            try:
                if upper_line in config.CONTROL_NAME_SET:
                    win_code = config.CONTROL_CHAR_NAMES[upper_line].value
                    log = f"第{line_num}行：{upper_line} {config.ARROW_RIGHT} {win_code} 🎛️"
                    print(f"{Style.BLUE}{log}{Style.RESET}")
                
                elif len(line) == 1:
                    if line in config.CHAR_TO_CODE:
                        win_code = config.CHAR_TO_CODE[line]
                    else:
                        win_code = ord(line.encode(config.start_file_encoding).decode(config.start_file_encoding))

                    if config.CODE_MIN <= win_code <= config.CODE_MAX:
                        display_char = line if line != " " else "[空格] 🚀"
                        log = f"第{line_num}行：{display_char} {config.ARROW_RIGHT} {win_code}"
                        print(f"{Style.WHITE}{log}{Style.RESET}")
                    else:
                        log = f"第{line_num}行：{line} {config.ARROW_RIGHT} 超出编码范围（{config.CODE_MIN}-{config.CODE_MAX}）⚠️"
                        print(f"{Style.YELLOW}{log}{Style.RESET}")
                
                else:
                    log = f"第{line_num}行：{line} {config.ARROW_RIGHT} 无效输入（仅支持单个字符或控制字符名称）❌"
                    print(f"{Style.RED}{log}{Style.RESET}")
                
                result_lines.append(log)
            
            except UnicodeEncodeError:
                log = f"第{line_num}行：{line} {config.ARROW_RIGHT} {config.converter_mode}模式不支持该字符 ❌"
                print(f"{Style.RED}{log}{Style.RESET}")
                result_lines.append(log)
            
            progress.update(1)
        
        progress.close()
        
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(result_lines))
            print(f"\n{Style.GREEN}结果已保存到：{output_path} 📥{Style.RESET}")
    
    except FileNotFoundError:
        print(f"{Style.RED}错误：输入文件不存在 ❌{Style.RESET}")
    except PermissionError:
        print(f"{Style.RED}错误：无权限读取输入文件 🚫{Style.RESET}")
    except Exception as e:
        print(f"{Style.RED}错误：批量编码过程失败 ❌ - {e}{Style.RESET}")
        print(traceback.format_exc())

# ------------------------------
# 字符串转换函数（整段文字/编码批量转换）
# ------------------------------
def string_convert(input_str: str, to_encode: bool = False) -> str:
    """字符串转换：将整段字符串在字符和编码值之间转换（按当前模式）"""
    result_list = []
    
    if to_encode:
        progress = tqdm(input_str, desc="编码字符 🔤→🔢", unit="字符", ncols=80)
        for char in progress:
            try:
                if char in config.CHAR_TO_CODE:
                    code = config.CHAR_TO_CODE[char]
                else:
                    code = ord(char.encode(config.start_file_encoding).decode(config.start_file_encoding))
                
                result_list.append(str(code))
            except UnicodeEncodeError:
                result_list.append(f"[不支持:{char}] ❌")
        progress.close()
        return " ".join(result_list)
    
    else:
        code_str_list = input_str.split()
        progress = tqdm(code_str_list, desc="解码编码值 🔢→🔤", unit="个", ncols=80)
        for code_str in progress:
            try:
                win_code = int(code_str)
                if not (config.CODE_MIN <= win_code <= config.CODE_MAX):
                    result_list.append(f"[无效:{code_str}] ❌")
                    continue
                
                if win_code in config.CONTROL_VALUE_SET:
                    result_list.append(f"[{config.CONTROL_CHAR_NAMES(win_code).name}]")
                else:
                    if config.converter_mode == "Windows1252":
                        char = config.WINDOWS1252_CHAR_MAP.get(win_code, chr(win_code))
                    else:
                        char = chr(win_code)
                    result_list.append(char)
            
            except ValueError:
                result_list.append(f"[非数字:{code_str}] ❌")
        progress.close()
        return "".join(result_list)

# ------------------------------
# 文件编码验证函数（检查文件是否符合当前模式编码）
# ------------------------------
def validate_file_encoding(file_path: str) -> bool:
    """验证文件是否与当前模式的编码兼容（无无效字符）"""
    current_encoding = config.start_file_encoding
    print(f"\n{Style.CYAN}=== 验证 {current_encoding.upper()} 编码兼容性 ✅==={Style.RESET}")
    
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        
        progress = tqdm(total=len(content), desc="检查字节 🔍", unit="字节", ncols=80)
        for byte in content:
            try:
                bytes([byte]).decode(current_encoding, errors="strict")
            except UnicodeDecodeError:
                progress.close()
                print(f"{Style.RED}错误：无效的 {current_encoding.upper()} 字节（0x{byte:02X}）❌，位置：{progress.n}{Style.RESET}")
                return False
            progress.update(1)
        
        progress.close()
        print(f"{Style.GREEN}{file_path} 完全兼容 {current_encoding.upper()} 编码 🎉{Style.RESET}")
        return True
    
    except FileNotFoundError:
        print(f"{Style.RED}错误：文件不存在 ❌{Style.RESET}")
        return False
    except PermissionError:
        print(f"{Style.RED}错误：无权限读取文件 🚫{Style.RESET}")
        return False
    except Exception as e:
        print(f"{Style.RED}错误：编码验证失败 ❌ - {e}{Style.RESET}")
        return False

# ------------------------------
# 转换字节函数
# ------------------------------
def str_to_bytes(prompt: str, mode: str):
    """获取字符串和模式，转换为字节"""
    byte_data = prompt.encode(encoding = mode)
    byte_list = [b for b in byte_data]
    byte_format = " ".join(str(byte) for byte in byte_list)
    print(f"{Style.BLUE}转换结果：{prompt} {config.ARROW_RIGHT} {Style.BRIGHT_GREEN}{byte_format}{Style.RESET}")

def bytes_to_str(prompt: str, mode: str):
    """获取字符串和模式，现将字符串转换为需要的字节，再转换为字符串"""
    str_list = prompt.strip().split()
    byte_list = [int(i) for i in str_list]
    byte_data = bytes(byte_list)
    chars = byte_data.decode(encoding = mode, errors="replace").replace("\ufffd", "[未分配]").replace("?", "[未分配]") 
    print(f"{Style.BLUE}转换结果：{prompt} {config.ARROW_RIGHT} {Style.BRIGHT_GREEN}{chars}{Style.RESET}")

# ------------------------------
# 设置/取消只读属性
# ------------------------------
def set_readonly(file_path, readonly=True):
    """设置文件为只读/取消只读"""
    file_path = Path(file_path)
    if not file_path.exists():
        return
    
    # Windows 系统（修改文件属性）
    if config.IS_WINDOWS:
        try:
            import win32api, win32con
        except:
            print("找不到库：pywin32", file=sys.stderr)
            sys.exit(1)

        # 获取当前文件属性
        attrs = win32api.GetFileAttributes(str(file_path))
        if readonly:
            # 添加只读属性
            attrs |= win32con.FILE_ATTRIBUTE_READONLY
        else:
            # 移除只读属性
            attrs &= ~win32con.FILE_ATTRIBUTE_READONLY
        win32api.SetFileAttributes(str(file_path), attrs)
    
    # macOS/Linux 系统（修改文件权限）
    else:
        import stat
        # 获取当前权限
        current_mode = os.stat(file_path).st_mode
        if readonly:
            # 移除写权限（所有者/组/其他都不能写）
            os.chmod(file_path, current_mode & ~stat.S_IWRITE)
        else:
            # 恢复写权限（所有者可写）
            os.chmod(file_path, current_mode | stat.S_IWRITE)

# ------------------------------
# 日志操作
# ------------------------------
def delete_log():
    rmtree("./src/assets/log")

def show_log():
    return open("./src/assets/log/codeconv.log", mode='w', encoding='utf-8')

# ------------------------------
# 主转换器界面（交互入口）
# ------------------------------
def dual_mode_converter():
    """双模式（Windows1252/ASCII）转换器主交互界面"""
    current_convert_mode = "解码"  # 初始转换模式（编码/解码）

    # 清屏
    print("\033[c")
    
    # 欢迎信息
    print("\n" + "="*60)
    print(f"{Style.BRIGHT_CYAN}{Style.BOLD}Windows-1252 / ASCII 转换器 v{config.VERSION} 🎉{Style.RESET}")
    print("="*60)
    print(f"{Style.BLUE}当前编码模式：{config.converter_mode}（有效编码范围：{config.CODE_MIN}-{config.CODE_MAX}）🌐{Style.RESET}")
    print(f"{Style.BLUE}使用说明：输入编码值/字符或中文命令（输入 '帮助' 查看所有可用命令）❓{Style.RESET}")
    print("="*60 + "\n")

    # 新加一个线程用来初始化
    Thread(target=init, name="codeconv_init").start()
    # 屏蔽Ctrl+C
    ignore_ctrl_c()

    try:
        # 主循环（持续接收用户输入）
        while True:
            try:
                # 命令提示符（简化格式）
                prompt = f"{Style.MAGENTA}{config.converter_mode} - {current_convert_mode} 请输入内容/命令 📥：{Style.RESET}"
                user_input = hotkey_cmd if hotkey_cmd else input(prompt).strip()
            
                # 处理空输入
                if not user_input:
                    print(f"{Style.RED}错误：输入不能为空 ❌{Style.RESET}")
                    continue
            
                # 处理命令和快捷键
                if user_input in config.COMMANDS:
                    match user_input.lower():
                        case"编码":
                            current_convert_mode = "编码"
                            print(f"{Style.GREEN}已切换到编码模式（字符→编码）🔤→🔢{Style.RESET}")
                        case "解码":
                            current_convert_mode = "解码"
                            print(f"{Style.GREEN}已切换到解码模式（编码→字符）🔢→🔤{Style.RESET}")
                        case "历史记录":
                            history = read_history()
                            print(f"\n{Style.CYAN}=== 操作历史记录 📜==={Style.RESET}")
                            if history:
                                for idx, record in enumerate(history, 1):
                                    print(f"{Style.WHITE}{idx}. {record}{Style.RESET}\n")
                                print(f"{Style.BLUE}总记录数：{len(history)}（最大限制：{config.MAX_HISTORY_COUNT}）📊{Style.RESET}")
                            else:
                                print(f"{Style.YELLOW}暂无历史记录 📭{Style.RESET}")
                            print("="*30 + "\n")
                        case "清空历史":
                            confirm = input(f"{Style.YELLOW}确定要清空历史记录吗？（yes/no）❓：{Style.RESET}").lower()
                            if confirm == "yes":
                                clear_history()
                            else:
                                print(f"{Style.BLUE}已取消清空历史记录操作 🚫{Style.RESET}")
                        case "清空输出":
                            if config.IS_WINDOWS:
                                run("cls", shell=True)
                            else:
                                run("clear", shell=True)
                            print(f"{Style.GREEN}输出已清空 🧹{Style.RESET}")
                        case "帮助" :
                            print(f"\n{Style.CYAN}=== 命令帮助文档 ❓==={Style.RESET}")
                            for cmd_name, cmd_desc in config.COMMANDS.items():
                                print(f"{Style.WHITE}  {cmd_name:<12} {cmd_desc}{Style.RESET}")
                            print("="*35 + "\n")
                        case "退出":
                            print(f"{Style.BRIGHT_GREEN}感谢使用本转换器，再见！👋{Style.RESET}")
                            INFO_VALUE = "请按任意键退出..."
                            input(INFO_VALUE)
                            break
                        case "所有命令":
                            print(f"\n{Style.CYAN}可用命令 📋：{Style.RESET}")
                            print(f"{Style.WHITE}{'、'.join(config.COMMANDS.keys())}{Style.RESET}")
                            print()
                        case "版本信息":
                            print(f"\n{Style.CYAN}=== 版本信息 📌==={Style.RESET}")
                            print(f"{Style.WHITE}转换器版本：v{config.VERSION}{Style.RESET}")
                            print(f"{Style.WHITE}Python版本：{sys.version.split()[0]}{Style.RESET}")
                            print(f"{Style.WHITE}操作系统：{config.SYSTEM_TYPE}{Style.RESET}")
                            print(f"{Style.WHITE}设备类型：{'移动设备 📱' if config.IS_MOBILE else '桌面设备 💻'}{Style.RESET}")
                            print("="*30 + "\n")
                        case "系统配置":
                            print(f"\n{Style.CYAN}=== 系统配置信息 ⚙️ ==={Style.RESET}")
                            print(f"{Style.WHITE}版本：v{config.VERSION}{Style.RESET}")
                            print(f"{Style.WHITE}当前编码模式：{config.converter_mode}{Style.RESET}")
                            print(f"{Style.WHITE}有效编码范围：{config.CODE_MIN}-{config.CODE_MAX}{Style.RESET}")
                            print(f"{Style.WHITE}文件编码：{config.start_file_encoding.upper()}{Style.RESET}")
                            print(f"{Style.WHITE}操作系统：{config.SYSTEM_TYPE}{Style.RESET}")
                            print(f"{Style.WHITE}移动设备：{'是 📱' if config.IS_MOBILE else '否 💻'}{Style.RESET}")
                            print(f"{Style.WHITE}历史文件路径：{config.HISTORY_FILE} 📁{Style.RESET}")
                            print(f"{Style.WHITE}最大历史记录数：{config.MAX_HISTORY_COUNT}{Style.RESET}")
                            print("="*35 + "\n")
                        case "作者信息":
                            print(f"\n{Style.CYAN}=== 作者信息 🧑 ==={Style.RESET}")
                            print(f"{Style.WHITE}作者名称：{config.AUTHOR}{Style.RESET}")
                            print(f"{Style.WHITE}作者年龄：{config.AGE}{Style.RESET}")
                        case "批量处理":
                            batch_mode = input(f"{Style.MAGENTA}请输入批量处理模式（编码/解码）🔤/🔢：{Style.RESET}").strip()
                            if batch_mode not in ["编码", "解码"]:
                                print(f"{Style.RED}错误：无效的批量模式 - 请输入 '编码' 或 '解码' ❌{Style.RESET}")
                                continue
                            file_path = input(f"{Style.MAGENTA}请输入输入文件路径 📥：{Style.RESET}").strip()
                            if not file_path:
                                print(f"{Style.RED}错误：输入文件路径不能为空 ❌{Style.RESET}")
                                continue
                            export = input(f"{Style.MAGENTA}是否要将结果保存到文件？（yes/no）💾：{Style.RESET}").lower()
                            output_path = input(f"{Style.MAGENTA}请输入输出文件路径 📤：{Style.RESET}").strip() if export == "yes" else None
                            if batch_mode == "解码":
                                batch_decode(file_path, output_path)
                            else:
                                batch_encode(file_path, output_path)
                            print()
                        case "字符串转换":
                            str_mode = input(f"{Style.MAGENTA}请输入字符串转换模式（编码/解码）🔤/🔢：{Style.RESET}").strip()
                            if str_mode not in ["编码", "解码"]:
                                print(f"{Style.RED}错误：无效的字符串模式 - 请输入 '编码' 或 '解码' ❌{Style.RESET}")
                                continue
                            input_str = input(f"{Style.MAGENTA}请输入要{str_mode}的字符串 📝：{Style.RESET}").strip()
                            if not input_str:
                                print(f"{Style.RED}错误：输入字符串不能为空 ❌{Style.RESET}")
                                continue
                            result = string_convert(input_str, to_encode=(str_mode == "编码"))
                            print(f"\n{Style.BLUE}转换结果：{input_str} {config.ARROW_RIGHT} {Style.BRIGHT_GREEN}{result} 🎉{Style.RESET}\n")
                            save_history(input_str, result, f"string_{str_mode}")
                        case "验证编码":
                            file_path = input(f"{Style.MAGENTA}请输入要验证的文件路径 📁：{Style.RESET}").strip()
                            if not file_path:
                                print(f"{Style.RED}错误：文件路径不能为空 ❌{Style.RESET}")
                                continue
                            validate_file_encoding(file_path)
                            print()
                        case "切换Windows1252":
                            config.converter_mode = "Windows1252"
                            print(f"{Style.GREEN}已切换到Windows-1252模式（编码范围0-255，支持更多字符）🌐{Style.RESET}")
                        case "切换ASCII":
                            config.converter_mode = "ASCII"
                            print(f"{Style.GREEN}已切换到ASCII模式（编码范围0-127，标准ASCII字符集）📟{Style.RESET}")
                        case "转换成字节":
                            converter_bytes_prompt = input("请输入要转换的字符串：")
                            while True:
                                converter_bytes_mode = input("请输入转换的编码：").strip().lower()
                                if converter_bytes_mode in config.SUPPORTED_DECODE_BYTES_MODES:
                                    break
                                print(f"{Style.RED}❌ 错误：请输入支持的编码模式！{Style.RESET}")
                            
                            str_to_bytes(converter_bytes_prompt, converter_bytes_mode)
                        case "转换成字符串":
                            while True:
                                count = 0
                                converter_bytes_prompt = input("请输入要转换的字节：").strip()
                                prompt_list = converter_bytes_prompt.strip().split()
                                for byte in prompt_list:
                                    byte = int(byte)
                                    if config.CODE_MIN <= byte <= config.CODE_MAX:
                                        count += 1
                                        continue
                                    else:
                                        print(f"{Style.RED}❌ 错误：请输入正确的字节范围！{Style.RESET}")
                                        break
                                if count == len(prompt_list):
                                    break

                            while True:
                                converter_bytes_mode = input("请输入转换的编码：").strip().lower()
                                if converter_bytes_mode in config.SUPPORTED_ENCODE_BYTES_MODES:
                                    break
                                print(f"{Style.RED}❌ 错误：请输入支持的编码模式！{Style.RESET}")
                            
                            bytes_to_str(converter_bytes_prompt, converter_bytes_mode)
                        case "日志":
                            print(f"\n{Style.CYAN}=== 日志内容 📃 ==={Style.RESET}")
                            print(show_log())
                        case "删除日志":
                            delete_log()
                
                
                else:
                    # 非命令输入，执行编码/解码
                    try:
                        if current_convert_mode == "解码":
                            # 尝试解码（支持多个编码值空格分隔）
                            if " " in user_input:
                                result = string_convert(user_input, to_encode=False)
                            else:
                                win_code = int(user_input)
                                if not (config.CODE_MIN <= win_code <= config.CODE_MAX):
                                    print(f"{Style.YELLOW}警告：编码值超出范围（{config.CODE_MIN}-{config.CODE_MAX}）⚠️{Style.RESET}")
                                    continue
                                if win_code in config.CONTROL_VALUE_SET:
                                    result = f"[控制字符:{config.CONTROL_CHAR_NAMES(win_code).name}] 🎛️"
                                else:
                                    result = config.WINDOWS1252_CHAR_MAP.get(win_code, chr(win_code)) if config.converter_mode == "Windows1252" else chr(win_code)
                            print(f"\n{Style.BLUE}解码结果：{user_input} {config.ARROW_RIGHT} {Style.BRIGHT_GREEN}{result} 🎉{Style.RESET}\n")
                            save_history(user_input, result, "decode")
                        else:
                            # 执行编码（单个字符或字符串）
                            result = string_convert(user_input, to_encode=True)
                            print(f"\n{Style.BLUE}编码结果：{user_input} {config.ARROW_RIGHT} {Style.BRIGHT_GREEN}{result} 🎉{Style.RESET}\n")
                            save_history(user_input, result, "encode")
                    except ValueError:
                        print(f"{Style.RED}错误：无效输入 - 解码模式请输入数字编码值，多个值用空格分隔 ❌{Style.RESET}")
                    except Exception as e:
                        print(f"{Style.RED}错误：转换失败 ❌ - {e}{Style.RESET}")
            except EOFError:
                print()
    except Exception as e:
        print(f"{Style.RED}错误：程序异常 ❌ - {e}{Style.RESET}")
        print(traceback.format_exc())

if __name__ == "__main__":
    # 定义计数文件路径
    count_path = Path(os.getcwd()) / "src" / "config" /  "count.txt"

    if not count_path.exists():
        with open(count_path, 'w', encoding="utf-8") as f:
            f.write("0")

    set_readonly(count_path, False)

    with open(count_path, 'r+', encoding="utf-8") as f:
        content = int(f.read())
        f.seek(0)
        f.write(str(content + 1))
        f.truncate()

    set_readonly(count_path, True)
    
    init_log()

    log.info(f"程序第{content}次成功运行 ✅")
    
    dual_mode_converter()