#!/usr/bin/env python3
"""语音转写: 把 Discord 的语音条变成文字, 这样你可以直接说话, 不用打字。

配置(环境变量, 都可选):
  AMY_STT_PYTHON  跑 mlx-whisper 的解释器(默认: 当前解释器)。别的项目里
                  已经装过 mlx-whisper 的话, 指向那个 venv 即可 —— 模型
                  缓存(~/.cache/huggingface)是共用的, 不必再下一份。
  AMY_STT_MODEL   模型 repo(默认 mlx-community/whisper-large-v3-turbo)
  AMY_STT_OFF     设成 1 就整个关掉, 语音条会被告知听不了

需要 Apple Silicon + mlx-whisper(`pip install mlx-whisper`)。没装也不影响
Amy 的其它功能, 只是收到语音条时她会说自己听不了。

转写跑在子进程里: 模型每次用完就随进程释放, 不常驻值班员的内存。
"""
import os
import pathlib
import re
import subprocess
import sys

PYTHON = os.environ.get("AMY_STT_PYTHON") or sys.executable
MODEL = os.environ.get("AMY_STT_MODEL", "mlx-community/whisper-large-v3-turbo")
TIMEOUT = int(os.environ.get("AMY_STT_TIMEOUT", "300"))

# 子进程里跑的转写脚本。condition_on_previous_text=False: 不把已输出的文本
# 喂回下一段解码, 斩断 Whisper 在结尾静音处「越重复越重复」的反馈循环。
_SNIPPET = """
import sys
import mlx_whisper
r = mlx_whisper.transcribe(sys.argv[1], path_or_hf_repo=sys.argv[2],
                           condition_on_previous_text=False)
sys.stdout.write(r["text"].strip())
"""


def available():
    """这台机器能不能转写(解释器里有没有 mlx_whisper)。"""
    if os.environ.get("AMY_STT_OFF") == "1":
        return False
    try:
        r = subprocess.run([PYTHON, "-c", "import mlx_whisper"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _collapse_repeats(text):
    """压掉 Whisper 结尾的重复幻觉: 同一短语连续重复 3 次以上压回 2 次。

    单元最长 40 字, 避免长串正则回溯拖慢。
    """
    if not text:
        return text
    return re.sub(r"(.{1,40}?)\1{2,}", lambda m: m.group(1) * 2, text)


def transcribe(path):
    """转写一个音频文件, 返回文字; 失败返回空串(调用方按"没听清"处理)。"""
    if os.environ.get("AMY_STT_OFF") == "1":
        return ""
    if not pathlib.Path(path).exists():
        return ""
    try:
        r = subprocess.run([PYTHON, "-c", _SNIPPET, str(path), MODEL],
                           capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"[stt] 转写超时(>{TIMEOUT}s): {path}", flush=True)
        return ""
    except Exception as e:
        print(f"[stt] 转写起不来: {e}", flush=True)
        return ""
    if r.returncode != 0:
        print(f"[stt] 转写失败: {(r.stderr or '').strip()[-200:]}", flush=True)
        return ""
    return _collapse_repeats(r.stdout.strip())


if __name__ == "__main__":                 # 手动试: python3 engine/stt.py a.ogg
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <音频文件>")
        print(f"解释器: {PYTHON}\n模型: {MODEL}\n可用: {available()}")
        sys.exit(1)
    print(transcribe(sys.argv[1]))
