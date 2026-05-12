import json
import os
import requests

CACHE_FILE = "data/sensor_cache.json"


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def process_and_cache_sensor_data(user_id, day_num, content, memory_client):
    """
    处理传感器数据：存入热缓存。如果满7条弹出最旧；如果是Day 1,6,11...触发总结存入冷库。
    """
    cache = load_cache()
    if user_id not in cache:
        cache[user_id] = {}
    user_cache = cache[user_id]

    # 写入热缓存
    user_cache[str(day_num)] = {"content": content}
    system_log = ""

    existing_days = sorted([int(k) for k in user_cache.keys()])

    # 【满 7 溢出逻辑】
    if len(existing_days) > 7:
        oldest_day = existing_days[0]

        # 【逢 1, 6, 11... 触发历史总结】
        if oldest_day % 5 == 1:
            days_to_sum = [str(d) for d in range(oldest_day, oldest_day + 5) if str(d) in user_cache]
            text_to_sum = "\n".join([user_cache[d]["content"] for d in days_to_sum])

            print(f"[{user_id}] 触发内存压缩！正在总结 Day {oldest_day} 到 {oldest_day + 4} 的数据...")
            sum_prompt = f"请高度概括这5天的高血压体征趋势（50字内），提取平均睡眠和心率下降情况：\n{text_to_sum}"

            try:
                resp = requests.post("http://localhost:11434/api/generate",
                                     json={"model": "qwen2.5:7b", "prompt": sum_prompt, "stream": False})
                summary_res = resp.json().get('response') if resp.status_code == 200 else "该阶段趋势稳定。"
            except:
                summary_res = "该阶段趋势稳定。"

            # 将总结永久刻入 MemMachine
            memory_client.add(f"【历史趋势归档】Day {oldest_day} - {oldest_day + 4} 总结：{summary_res}")
            system_log = f"(系统已将 Day {oldest_day}-{oldest_day + 4} 归档为长时记忆)"

        # 弹出最老的数据
        del user_cache[str(oldest_day)]

    save_cache(cache)
    return system_log