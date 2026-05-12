from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import requests
import json
import re
from memmachine_client import MemMachineClient
from cache_manager import load_cache, process_and_cache_sensor_data  # 引入模块

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
client = MemMachineClient(base_url="http://localhost:8080")

pending_alerts = {}


class SensorData(BaseModel):
    user_id: str
    sleep_hours: Optional[float] = None
    awakenings: Optional[int] = None
    day_hr: Optional[int] = None
    night_hr: Optional[int] = None
    steps: Optional[int] = None
    current_day: str


class ChatData(BaseModel):
    user_id: str
    message: str


def get_user_memory(user_id: str):
    project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{user_id}")
    return project.memory(group_id="default", agent_id="health_bot", user_id=user_id, session_id="live_session")


@app.get("/api/users")
def get_users():
    cache = load_cache()
    return {"users": list(cache.keys())}  # 直接从缓存读取已有用户


@app.get("/api/get_alert")
def get_alert(user_id: str):
    return {"alert": pending_alerts.pop(user_id, None)}


@app.post("/api/inject_and_analyze")
def inject_and_analyze(data: SensorData):
    day_match = re.search(r'\d+', data.current_day)
    day_num = int(day_match.group()) if day_match else 1

    cache = load_cache()
    user_cache = cache.get(data.user_id, {})
    existing_days = sorted([int(k) for k in user_cache.keys()])
    max_day = existing_days[-1] if existing_days else 0

    if existing_days and day_num < max_day - 1:
        return {"status": "error", "ai_alert": f"系统安全限制：不支持覆盖 Day {max_day - 1} 之前的历史传感器数据。"}

    is_non_dipper = False
    if data.day_hr is not None and data.night_hr is not None and data.day_hr > 0:
        hr_drop = ((data.day_hr - data.night_hr) / data.day_hr) * 100
        is_non_dipper = hr_drop < 20
        hr_desc = f"日间心率{data.day_hr}，夜间心率{data.night_hr}。" + (
            f"夜间心率下降仅{hr_drop:.1f}%(非勺型危险)" if is_non_dipper else "")
    else:
        hr_desc = "心率数据不完整。"

    sleep_desc = f"睡眠{data.sleep_hours}h" if data.sleep_hours is not None else "睡眠未知"
    awake_desc = f"起夜{data.awakenings}次" if data.awakenings is not None else "起夜未知"

    record = f"【Day {day_num}】{sleep_desc}，{awake_desc}。{hr_desc}"

    memory = get_user_memory(data.user_id)
    # 【调用模块，处理溢出和归档】
    system_log = process_and_cache_sensor_data(data.user_id, day_num, record, memory)

    # 重新加载最新缓存
    user_cache = load_cache().get(data.user_id, {})
    results = memory.search("检索我的基础画像以及历史趋势总结")

    context = ""
    try:
        if results.content.semantic_memory:
            context += "【长期静态病史】\n" + "\n".join([f"- {s}" for s in results.content.semantic_memory]) + "\n"
        if results.content.episodic_memory.long_term_memory.episodes:
            context += "【历史压缩记忆(MemMachine LTM)】\n" + "\n".join(
                [f"- {ep.content}" for ep in results.content.episodic_memory.long_term_memory.episodes[:3]]) + "\n"
    except:
        pass

    context += "【最近 7 天精确体征(Hot Cache)】\n"
    for d in sorted([int(k) for k in user_cache.keys()]):
        context += f"- {user_cache[str(d)]['content']}\n"

    print(context)
    print('\n')

    prompt = f"你是端侧预警助手。根据病史和体征，对今天(Day {day_num})的数据进行风险评估。出现危险请立刻警告(80字内)：\n{context}"
    resp = requests.post("http://localhost:11434/api/generate",
                         json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False})

    print(resp.json())
    print('\n')

    pending_alerts[data.user_id] = resp.json().get('response', "分析失败") + system_log
    return {"status": "success"}


@app.post("/api/chat")
def chat(data: ChatData):
    memory = get_user_memory(data.user_id)
    results = memory.search(data.message)
    context = ""
    try:
        # 【修复问题2：全面检索 Semantic + LTM + STM】
        if results.content.semantic_memory:
            context += "【病史】\n" + "\n".join([f"- {s}" for s in results.content.semantic_memory]) + "\n"
        if results.content.episodic_memory.long_term_memory.episodes:
            context += "【历史对话与总结】\n" + "\n".join(
                [f"- {ep.content}" for ep in results.content.episodic_memory.long_term_memory.episodes[:3]]) + "\n"
        if results.content.episodic_memory.short_term_memory.episodes:
            context += "【近期对话】\n" + "\n".join(
                [f"- {ep.content}" for ep in results.content.episodic_memory.short_term_memory.episodes]) + "\n"
    except:
        pass

    cache = load_cache().get(data.user_id, {})
    if cache:
        context += "【最近传感器体征】\n"
        for d in sorted([int(k) for k in cache.keys()]): context += f"- {cache[str(d)]['content']}\n"

    print(context)
    print('\n')

    prompt = f"你是医疗助手。请结合记忆回答。{context}\n\n用户提问：{data.message}\n回答："
    resp = requests.post("http://localhost:11434/api/generate",
                         json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False})
    ai_reply = resp.json().get('response', "请求失败")

    print(ai_reply)
    print('\n')

    # 【修复问题2核心：将真实对话存入 MemMachine，形成真正的记忆流闭环！】
    memory.add(f"[用户咨询]：{data.message}\n[系统回复]：{ai_reply}")

    return {"reply": ai_reply}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)