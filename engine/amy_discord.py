#!/usr/bin/env python3
"""Amy 的 Discord 值班员: 专属频道或私聊 DM 收发消息, 手机上随时找她。

配置(环境变量, 没配就不上岗):
  AMY_DISCORD_TOKEN    Discord bot 的 token(建一个叫 Amy 的新 bot, 和其他 bot 分开)
  AMY_DISCORD_CHANNEL  频道模式: Amy 专属频道的 ID
  AMY_DISCORD_USER     DM 模式: 你自己的用户 ID(bot 会自动开一条私聊线;
                       需要你和 bot 至少同在一个服务器)
  两者给一个即可; 都给则优先频道。

轮询模式(每 5 秒), 不需要公网; 消息进出都走与桌面同一份聊天历史,
手机聊的桌面能看到, 桌面聊的手机也有记录。DM 里说话不需要 @。
"""
import base64
import json
import os
import pathlib
import secrets
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import secretary
import server as srv

TOK = os.environ.get("AMY_DISCORD_TOKEN")
CHANNEL = os.environ.get("AMY_DISCORD_CHANNEL")
USER = os.environ.get("AMY_DISCORD_USER")
STATE_F = pathlib.Path(__file__).resolve().parents[1] / "runtime/discord_state.json"


def resolve_channel(tok, channel=None, user=None):
    """频道 ID 直接用; 只给用户 ID 则向 Discord 开一条 DM 线并返回它的频道 ID。"""
    if channel:
        return channel
    if not user:
        return None
    r = subprocess.run(
        ["curl", "-s", "--max-time", "15", "-X", "POST",
         "-H", f"Authorization: Bot {tok}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"recipient_id": str(user)}),
         "https://discord.com/api/v10/users/@me/channels"],
        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout).get("id")
    except json.JSONDecodeError:
        return None


def api(path, extra=None):
    cmd = ["curl", "-s", "--max-time", "15",
           "-H", f"Authorization: Bot {TOK}",
           "https://discord.com/api/v10" + path]
    if extra:
        cmd = cmd[:1] + extra + cmd[1:]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def send(tok, channel, text):
    """长文本分条发(Discord 单条上限 2000)。供本模块与 morning_call 复用。

    用 JSON body + stdin 传参: -F 表单模式会把文本里的分号当属性分隔符,
    消息带 ';' 就发不出去(实测踩坑)。
    """
    for i in range(0, max(len(text), 1), 1900):
        payload = json.dumps({"content": text[i:i + 1900]}, ensure_ascii=False)
        subprocess.run(
            ["curl", "-s", "--max-time", "30",
             "-H", f"Authorization: Bot {tok}",
             "-H", "Content-Type: application/json",
             "--data-binary", "@-",
             f"https://discord.com/api/v10/channels/{channel}/messages"],
            input=payload.encode(), capture_output=True, timeout=60)


# ---------- 绿点: gateway 报到心跳(纯标准库迷你 websocket) ----------
# 轮询收发不需要它; 它唯一的工作是保持一条到 Discord 的长连接, 让头像亮绿灯。
# 挂了就退避重连; 彻底失败也只影响绿点, 不影响消息。AMY_DISCORD_PRESENCE=off 可关。

def _ws_connect(url_host, path):
    raw = socket.create_connection((url_host, 443), timeout=15)
    sk = ssl.create_default_context().wrap_socket(raw, server_hostname=url_host)
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    sk.sendall((f"GET {path} HTTP/1.1\r\nHost: {url_host}\r\n"
                f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    hdr = b""
    while b"\r\n\r\n" not in hdr:
        chunk = sk.recv(4096)
        if not chunk:
            raise ConnectionError("handshake EOF")
        hdr += chunk
    if b" 101 " not in hdr.split(b"\r\n", 1)[0]:
        raise ConnectionError("handshake rejected")
    return sk


def _ws_send(sk, payload, opcode=0x1):
    data = payload.encode() if isinstance(payload, str) else payload
    mask = secrets.token_bytes(4)
    n = len(data)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", n)
    sk.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))


def _recv_exact(sk, n):
    buf = b""
    while len(buf) < n:
        chunk = sk.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("EOF")
        buf += chunk
    return buf


def _ws_recv(sk):
    """收一帧; 返回 (opcode, payload)。超时抛 socket.timeout。"""
    b1, b2 = _recv_exact(sk, 2)
    opcode = b1 & 0x0F
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", _recv_exact(sk, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", _recv_exact(sk, 8))[0]
    return opcode, _recv_exact(sk, n) if n else b""


def presence_loop(tok):
    backoff = 5
    while True:
        try:
            sk = _ws_connect("gateway.discord.gg", "/?v=10&encoding=json")
            sk.settimeout(1.0)
            op, data = None, b""
            while True:                                    # 等 HELLO
                op, data = _ws_recv(sk)
                if op == 0x1:
                    break
            interval = json.loads(data)["d"]["heartbeat_interval"] / 1000
            _ws_send(sk, json.dumps({"op": 2, "d": {
                "token": tok, "intents": 0,
                "properties": {"os": "macos", "browser": "tellmetickme",
                               "device": "tellmetickme"},
                "presence": {"status": "online", "since": None, "afk": False,
                             "activities": [{"name": "your todos", "type": 3}]},
            }}))
            print("绿点已点亮 (gateway 在线)", flush=True)
            backoff = 5
            seq = None
            next_beat = time.time() + interval * 0.9
            while True:
                if time.time() >= next_beat:
                    _ws_send(sk, json.dumps({"op": 1, "d": seq}))
                    next_beat = time.time() + interval
                try:
                    op, data = _ws_recv(sk)
                except socket.timeout:
                    continue
                if op == 0x9:                              # ws ping → pong
                    _ws_send(sk, data, opcode=0xA)
                elif op == 0x8:                            # close
                    raise ConnectionError("server closed")
                elif op == 0x1 and data:
                    msg = json.loads(data)
                    if msg.get("s") is not None:
                        seq = msg["s"]
                    if msg.get("op") == 1:                 # 服务器讨心跳
                        _ws_send(sk, json.dumps({"op": 1, "d": seq}))
                    elif msg.get("op") in (7, 9):          # 要求重连
                        raise ConnectionError("reconnect requested")
        except Exception as e:
            print(f"绿点线掉了({e}), {backoff}s 后重连", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


def state():
    try:
        return json.loads(STATE_F.read_text())
    except Exception:
        return {}


def save_state(st):
    STATE_F.parent.mkdir(parents=True, exist_ok=True)
    STATE_F.write_text(json.dumps(st))


def main():
    if not TOK or not (CHANNEL or USER):
        print("AMY_DISCORD_TOKEN + (AMY_DISCORD_CHANNEL 或 AMY_DISCORD_USER) 没配, "
              "Discord 值班不启动")
        return
    channel = resolve_channel(TOK, CHANNEL, USER)
    if not channel:
        print("DM 频道解析失败: 确认 bot 和你同在一个服务器、你的隐私设置允许成员私信")
        return
    st = state()
    print(f"Amy Discord 值班中 · {'DM' if not CHANNEL else 'channel'}={channel}", flush=True)
    if os.environ.get("AMY_DISCORD_PRESENCE", "on") != "off":
        threading.Thread(target=presence_loop, args=(TOK,), daemon=True).start()
    while True:
        try:
            after = f"?after={st['last_id']}" if st.get("last_id") else "?limit=1"
            msgs = api(f"/channels/{channel}/messages{after}")
            if isinstance(msgs, list) and msgs:
                for m in sorted(msgs, key=lambda x: int(x["id"])):
                    st["last_id"] = m["id"]
                    save_state(st)
                    if m.get("author", {}).get("bot"):
                        continue                      # 自己(或其它 bot)的消息不接
                    if USER and m.get("author", {}).get("id") != str(USER):
                        continue                      # 只听配置的这一位用户
                    text = (m.get("content") or "").strip()
                    if not text:
                        continue
                    srv.ensure_todo()
                    todo_text, _ = srv.read_todo()
                    done = [f"- {d['time']} 【{d['section']}】{d['text']}"
                            for d in srv.parse_done_today()]
                    print(f"DM 收到: {text[:50]}", flush=True)
                    try:
                        reply, sugg = secretary.chat(text, todo_text, done)
                    except Exception as e:
                        secretary.log_error(str(e))
                        reply, sugg = f"(出错了: {e})", []
                    print(f"DM 已回: {reply[:50]}", flush=True)
                    if sugg:
                        reply += ("\n\n(有 " + str(len(sugg)) +
                                  " 条待办建议, 在桌面小窗里点确认)")
                    send(TOK, channel, reply)
        except Exception as e:
            print("loop error:", e, flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
