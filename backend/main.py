from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import os
from memmachine_client import MemMachineClient

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
client = MemMachineClient(base_url="http://localhost:8080")


class SensorData(BaseModel):
    user_id: str
    sleep_hours: float
    awakenings: int
    day_hr: int
    night_hr: int
    steps: int
    current_day: str


class ChatData(BaseModel):
    user_id: str
    message: str


def get_user_memory(user_id: str):
    project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{user_id}")
    return project.memory(group_id="default", agent_id="health_bot", user_id=user_id, session_id="live_session")


# 【动态获取已注入的用户列表】
@app.get("/api/users")
def get_users():
    users = set()
    # 从本地数据集文件里提取用户列表，确保与后台一致
    try:
        with open("data/sft_dataset.json", "r", encoding="utf-8") as f:
            for item in json.load(f):
                if "user_id" in item: users.add(item["user_id"])
    except:
        pass
    users.add("stress_non_dipper_10days_user")  # 那个10天数据集的专属用户
    return {"users": list(users)}


# 【辅助函数：强制时间线排序】
def sort_episodes_chronologically(episodes_list):
    # 根据注入时的格式 [Day X] 或 [Latest] 强制排序
    # 这里用一个简单的字符串排序，确保 Day 1 在前，Day 10 在后
    return sorted(episodes_list, key=lambda x: x.content)


@app.post("/api/inject_and_analyze")
def inject_and_analyze(data: SensorData):
    memory = get_user_memory(data.user_id)

    # 规则引擎计算
    hr_drop_pct = ((data.day_hr - data.night_hr) / data.day_hr) * 100 if data.day_hr > 0 else 0
    is_non_dipper = hr_drop_pct < 20

    # 注入数据，打上明确的时间标签
    record = f"【{data.current_day}】睡眠{data.sleep_hours}小时，起夜{data.awakenings}次。日间心率{data.day_hr}，夜间心率{data.night_hr}。"
    if is_non_dipper:
        record += f"夜间心率下降不足20%，呈高危非勺型特征！"
    memory.add(record)

    # 检索并强制排序
    results = memory.search("检索我所有的历史体征数据、血压病史以及近期的心率表现。")
    context = ""
    try:
        if results.content.semantic_memory:
            context += "【长期病史】\n" + "\n".join([f"- {s}" for s in results.content.semantic_memory]) + "\n"

        # 提取短期记忆并【强制时间序列排序】
        if results.content.episodic_memory.short_term_memory.episodes:
            sorted_stm = sort_episodes_chronologically(results.content.episodic_memory.short_term_memory.episodes)
            context += "【按时间排序的历史体征】\n" + "\n".join([f"- {ep.content}" for ep in sorted_stm]) + "\n"
    except:
        pass

    prompt = f"""你是一个端侧高血压预警助手。请仔细阅读以下按时间排序的病历和体征数据。
如果发现患者最近几天呈现“非勺型特征”或起夜频繁，必须结合长期病史发出严重警告。

{context}
请直接给出一段专业的预警和用药/生活建议："""

    # ==================== 调试代码 ======================
    print("\n" + "=".rjust(60, "="))
    print(f"🎯 [当前操作用户]: {data.user_id}")
    print(f"📥 [实际检索到的记忆 Context]:\n{context}")
    print("-" * 60)
    print(f"🧠 [最终拼接好喂给 Qwen 的完整 Prompt]:\n{prompt}")
    print("=".rjust(60, "=") + "\n")
    # ==================================================

    resp = requests.post("http://localhost:11434/api/generate",
                         json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False})
    return {"status": "success",
            "ai_alert": resp.json().get('response') if resp.status_code == 200 else "大模型连接失败"}


@app.post("/api/chat")
def chat(data: ChatData):
    memory = get_user_memory(data.user_id)
    results = memory.search(data.message)
    context = ""
    try:
        if results.content.semantic_memory:
            context += "【病史】\n" + "\n".join([f"- {s}" for s in results.content.semantic_memory]) + "\n"
        if results.content.episodic_memory.short_term_memory.episodes:
            sorted_stm = sort_episodes_chronologically(results.content.episodic_memory.short_term_memory.episodes)
            context += "【近期状态】\n" + "\n".join([f"- {ep.content}" for ep in sorted_stm]) + "\n"
    except:
        pass

    prompt = f"你是医疗助手。请结合记忆回答。{context}\n\n问题：{data.message}\n回答："

    # ==================== 调试代码 ======================
    print("\n" + "=".rjust(60, "="))
    print(f"🎯 [当前操作用户]: {data.user_id}")
    print(f"📥 [实际检索到的记忆 Context]:\n{context}")
    print("-" * 60)
    print(f"🧠 [最终拼接好喂给 Qwen 的完整 Prompt]:\n{prompt}")
    print("=".rjust(60, "=") + "\n")
    # ==================================================

    resp = requests.post("http://localhost:11434/api/generate",
                         json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False})
    return {"reply": resp.json().get('response') if resp.status_code == 200 else "失败"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)