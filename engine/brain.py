"""Amy 的大脑接入层: 三条通道, 用户自己的 LLM 自己选。

  claude-code  已装 Claude Code 的用户 (订阅内合规, 功能最全: Amy 能检索
               资料库、自己维护记忆文件; 会话记忆走 --continue)
  api          Anthropic API key (无工具; 会话记忆走本地滚动历史)
  ollama       本地模型, 零成本全离线 (无工具; 会话记忆走本地滚动历史)

配置在 config/llm.json (网页首跑向导会生成), 环境变量可覆盖。
本项目不做任何「订阅搭车」式第三方接入, 三条通道全是正规门。
"""
import json
import os
import pathlib
import shutil
import subprocess
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
LLM_CONF = ROOT / "config/llm.json"
RUNTIME = ROOT / "runtime"
HIST_CAP = 40


def load_conf():
    try:
        return json.loads(LLM_CONF.read_text())
    except Exception:
        return {}


def save_conf(conf):
    LLM_CONF.parent.mkdir(parents=True, exist_ok=True)
    LLM_CONF.write_text(json.dumps(conf, ensure_ascii=False, indent=1))


def provider():
    """环境变量 > 配置文件 > 未配置。"""
    return os.environ.get("TMTM_PROVIDER") or load_conf().get("provider") or ""


def claude_bin():
    p = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if p:
        return p
    for c in (pathlib.Path.home() / ".local/bin/claude",
              pathlib.Path("/opt/homebrew/bin/claude"),
              pathlib.Path("/usr/local/bin/claude")):
        if c.exists():
            return str(c)
    return None


def detect():
    """给首跑向导用: 探测本机有哪些可用通道。"""
    out = {"claude_code": bool(claude_bin()), "ollama": False}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            out["ollama"] = r.status == 200
    except Exception:
        pass
    return out


def _post_json(url, payload, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _hist_file(session):
    return RUNTIME / f"history_{session}.json"


def _load_hist(session):
    try:
        return json.loads(_hist_file(session).read_text())
    except Exception:
        return []


def _save_hist(session, hist):
    _hist_file(session).parent.mkdir(parents=True, exist_ok=True)
    _hist_file(session).write_text(json.dumps(hist[-HIST_CAP:], ensure_ascii=False))


def think_api(text, persona, session):
    conf = load_conf()
    key = os.environ.get("ANTHROPIC_API_KEY") or conf.get("api_key")
    if not key:
        raise RuntimeError("api 通道没有 key (config/llm.json 或环境变量 ANTHROPIC_API_KEY)")
    hist = _load_hist(session) + [{"role": "user", "content": text}]
    out = _post_json("https://api.anthropic.com/v1/messages",
                     {"model": conf.get("model") or "claude-sonnet-5",
                      "max_tokens": 1500, "system": persona, "messages": hist},
                     {"x-api-key": key, "anthropic-version": "2023-06-01"})
    reply = "".join(b.get("text", "") for b in out.get("content", [])
                    if b.get("type") == "text").strip()
    if reply:
        _save_hist(session, hist + [{"role": "assistant", "content": reply}])
    return reply


def think_ollama(text, persona, session):
    conf = load_conf()
    url = conf.get("ollama_url") or "http://127.0.0.1:11434"
    model = conf.get("model") or "qwen3"
    hist = _load_hist(session) + [{"role": "user", "content": text}]
    out = _post_json(url.rstrip("/") + "/api/chat",
                     {"model": model, "stream": False,
                      "messages": [{"role": "system", "content": persona}] + hist}, {})
    reply = (out.get("message") or {}).get("content", "").strip()
    if reply:
        _save_hist(session, hist + [{"role": "assistant", "content": reply}])
    return reply
