import json
import time
from memmachine_client import MemMachineClient


# 【核心辅助函数：安全处理 null 缺失值】
def safe_get(dictionary, key, suffix=""):
    # 如果整个字典本身就是 None（比如传感器没开启），直接返回未知
    if dictionary is None:
        return "未知"
    val = dictionary.get(key)
    # 只有当值真的存在且不为 None 时，才拼接后缀
    return f"{val}{suffix}" if val is not None else "未知"


def init_database():
    client = MemMachineClient(base_url="http://localhost:8080")
    print("开始初始化底层隔离数据库并注入【长期病历】与【历史体征序列】...")

    # ==========================================
    # 1. 注入多用户单日数据集 (sft_dataset.json)
    # ==========================================
    try:
        with open("data/sft_dataset.json", "r", encoding="utf-8") as f:
            datasets = json.load(f)
            for data in datasets:
                user_id = data.get("user_id", "unknown_user")
                project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{user_id}")
                memory = project.memory(group_id="default", agent_id="health_bot", user_id=user_id,
                                        session_id="init_session")

                # 注入画像
                traits = data["input_context"]["user_traits"]
                memory.add(
                    f"【基本画像】年龄{traits['age_years']}岁，性别{traits['sex']}，BMI {traits['bmi']}。血压表型倾向：{traits.get('bp_phenotype_hint', '未知')}")

                # 注入单日历史体征，安全处理缺失值
                if "sensor_data_short_term" in data["input_context"]:
                    sensor = data["input_context"]["sensor_data_short_term"] or {}
                    day = data.get("day", "Day 1")
                    day_formatted = day.replace("Day ", "Day 0") if len(day) == 5 else day

                    sleep = sensor.get("sleep", {})
                    vitals = sensor.get("vitals_summary", {})

                    slp_hrs = safe_get(sleep, 'total_sleep_hours', 'h')
                    awake = safe_get(sleep, 'awakenings_count', '次')
                    day_hr = safe_get(vitals, 'resting_hr_bpm_day_mean')
                    night_hr = safe_get(vitals, 'resting_hr_bpm_night_mean')

                    memory.add(
                        f"[{day_formatted}] 历史体征记录：睡眠{slp_hrs}，起夜{awake}。日间心率{day_hr}，夜间心率{night_hr}。")
                print(f"✅ 用户 {user_id} 基础数据注入完成！")
    except Exception as e:
        print(f"加载 dataset 报错: {e}")

    # ==========================================
    # 2. 注入带有【缺失值】的 10天连贯数据集
    # ==========================================
    try:
        TEN_DAYS_USER = "stress_non_dipper_10days_user"
        project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{TEN_DAYS_USER}")
        memory = project.memory(group_id="default", agent_id="health_bot", user_id=TEN_DAYS_USER,
                                session_id="init_session")

        # 【修改点】：直接使用你上传的带有 missing 缺失值的 JSON 文件测试
        file_path = "data/sft_stress_single_user_10days_missing_aug_rate5.json"

        with open(file_path, "r", encoding="utf-8") as f:
            ten_days_data = json.load(f)

            # 第一天的画像作为基线注入
            base_traits = ten_days_data[0]["input_context"]["user_traits"]
            memory.add(
                f"【基本画像】年龄{base_traits['age_years']}岁，性别{base_traits['sex']}，BMI {base_traits['bmi']}。血压倾向：{base_traits.get('bp_phenotype_hint')}")

            # 严格按时间序列注入连续 10 天的体征（修复了缺失值解析！）
            for day_data in ten_days_data:
                sensor = day_data["input_context"].get("sensor_data_short_term", {}) or {}
                day = day_data.get("day", "Day 1")
                day_formatted = day.replace("Day ", "Day 0") if len(day) == 5 else day

                sleep = sensor.get("sleep", {})
                vitals = sensor.get("vitals_summary", {})

                # 【关键修复】：后半部分同样使用 safe_get 处理这 10 天内随时可能出现的 null
                slp_hrs = safe_get(sleep, 'total_sleep_hours', 'h')
                awake = safe_get(sleep, 'awakenings_count', '次')
                day_hr = safe_get(vitals, 'resting_hr_bpm_day_mean')
                night_hr = safe_get(vitals, 'resting_hr_bpm_night_mean')

                memory.add(
                    f"[{day_formatted}] 历史传感器记录：睡眠{slp_hrs}，起夜{awake}。日间心率{day_hr}，夜间心率{night_hr}。")

        print(f"✅ 10天连续演变用户 ({TEN_DAYS_USER}) 时序数据注入完成 (包含缺失值处理)！")
    except Exception as e:
        print(f"加载 10days 缺失数据集报错: {e}")


if __name__ == "__main__":
    init_database()