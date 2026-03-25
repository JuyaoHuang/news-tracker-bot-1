#!/usr/bin/env python3
"""
用于测试 TrendRadar AI 分析的 OpenAI 兼容端点的一次性脚本。

用途：
1) 编辑“CONFIG”部分中的常量。
2）运行：python脚本/check_ai_base_url_once.py
3) 选择建议的 api_base 并将其写入 config/config.yaml -> ai.api_base
"""

from __future__ import annotations

import json
from typing import List
from urllib.parse import urlsplit, urlunsplit

import requests


# =========================
# CONFIG（仅在此处编辑）
# =========================
# RAW_BASE_URL = "https://newapi.june.cc.cd"  # 示例：https://xxx.com 或 https://xxx.com/v1
# API_KEY = "sk-fB51izTbESkfNQxacCqwVPaUWVSPAhBD0odOcnxUOABncszW"
# RAW_BASE_URL = "https://wzw.pp.ua"  # 示例：https://xxx.com 或 https://xxx.com/v1
# API_KEY = "sk-RAvxOtkENv55NOlz1lSMkQaCLWBWmY22y7fDSZTkrXAfvFtX"
RAW_BASE_URL = "https://sub.jlypx.de"  # 示例：https://xxx.com 或 https://xxx.com/v1
API_KEY = "sk-22b1a907ed36e12b300d1439cfcf5daeeb927c18e5540bacb1a922ba70bfc5b1"
MODEL = "openai/gpt-5.3-codex"  # 与项目配置保持一致
TEMPERATURE = 1.0
MAX_TOKENS = 800
TIMEOUT_SECONDS = 45
VERIFY_SSL = True

# 端点探测的最小有效负载。
SYSTEM_PROMPT = "You are a concise analyst."
USER_PROMPT = (
    "Return strict JSON only: "
    '{"core_trends":"ok","sentiment_controversy":"","signals":"","rss_insights":"","outlook_strategy":"","standalone_summaries":{}}'
)


def _strip_provider_prefix(model: str) -> str:
    # LiteLLM 接受提供商/模型； OpenAI 兼容端点通常只需要模型。
    return model.split("/", 1)[1] if "/" in model else model


def _normalize_base(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _join_path(base: str, path: str) -> str:
    parts = urlsplit(base)
    merged_path = f"{parts.path.rstrip('/')}/{path.lstrip('/')}"
    return urlunsplit((parts.scheme, parts.netloc, merged_path, parts.query, parts.fragment))


def _candidate_chat_endpoints(base_url: str) -> List[str]:
    base = _normalize_base(base_url)
    if not base:
        return []

    out: List[str] = []
    if base.endswith("/chat/completions"):
        out.append(base)
    else:
        out.append(_join_path(base, "/chat/completions"))
        if not base.endswith("/v1"):
            out.append(_join_path(base, "/v1/chat/completions"))

    dedup: List[str] = []
    seen = set()
    for item in out:
        if item not in seen:
            dedup.append(item)
            seen.add(item)
    return dedup


def _extract_error_snippet(resp: requests.Response) -> str:
    text = resp.text or ""
    try:
        data = resp.json()
    except Exception:
        return text[:600]

    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("type") or json.dumps(err, ensure_ascii=False)
            return str(msg)[:600]
        if err is not None:
            return str(err)[:600]
    return text[:600]


def _extract_success_snippet(resp: requests.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        return (resp.text or "")[:400]

    # OpenAI 风格的聊天完成
    if isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content[:400]
    return json.dumps(data, ensure_ascii=False)[:400]


def main() -> None:
    base = _normalize_base(RAW_BASE_URL)
    if not base:
        raise SystemExit("RAW_BASE_URL is empty.")
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        raise SystemExit("Please set API_KEY in script before running.")

    request_model = _strip_provider_prefix(MODEL)
    endpoints = _candidate_chat_endpoints(base)
    payload = {
        "model": request_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print("=== Probe Config ===")
    print(f"RAW_BASE_URL: {RAW_BASE_URL}")
    print(f"MODEL(config): {MODEL}")
    print(f"MODEL(request): {request_model}")
    print(f"TIMEOUT: {TIMEOUT_SECONDS}s")
    print("\n=== Payload ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\n=== Endpoint Probe ===")

    success_endpoint = ""
    for idx, ep in enumerate(endpoints, start=1):
        print(f"\n[{idx}] POST {ep}")
        try:
            resp = requests.post(
                ep,
                headers=headers,
                json=payload,
                timeout=TIMEOUT_SECONDS,
                verify=VERIFY_SSL,
            )
        except requests.RequestException as e:
            print(f"Request error: {type(e).__name__}: {e}")
            continue

        print(f"HTTP {resp.status_code}")
        if 200 <= resp.status_code < 300:
            success_endpoint = ep
            print("Result: SUCCESS")
            print("Response snippet:")
            print(_extract_success_snippet(resp))
        else:
            print("Result: FAILED")
            print("Error snippet:")
            print(_extract_error_snippet(resp))

    print("\n=== Suggestion ===")
    if success_endpoint:
        if success_endpoint.endswith("/v1/chat/completions"):
            suggested_api_base = success_endpoint[: -len("/chat/completions")]
        else:
            suggested_api_base = success_endpoint[: -len("/chat/completions")]
        print(f"Use ai.api_base = {suggested_api_base}")
    else:
        print("No endpoint worked. Check API key, model name, provider compatibility, or network.")


if __name__ == "__main__":
    main()
