import json
import time
from memmachine_client import MemMachineClient


def init_database():
    client = MemMachineClient(base_url="http://localhost:8080")
    print("开始初始化底层隔离数据库并注入【长期病历】与【历史体征序列】...")

    # 1. 注入多用户单日数据集 (sft_dataset.json)
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

                # 【修复2：注入历史体征数据】
                if "sensor_data_short_term" in data["input_context"]:
                    sensor = data["input_context"]["sensor_data_short_term"]
                    day = data.get("day", "Day 1")
                    # 补齐不足两位的数字，如 Day 1 变成 Day 01，方便后续字符串时间线排序
                    day_formatted = day.replace("Day ", "Day 0") if len(day) == 5 else day

                    sleep = sensor.get("sleep", {})
                    vitals = sensor.get("vitals_summary", {})
                    memory.add(
                        f"[{day_formatted}] 历史传感器记录：睡眠{sleep.get('total_sleep_hours')}h，起夜{sleep.get('awakenings_count')}次。日间心率{vitals.get('resting_hr_bpm_day_mean')}，夜间心率{vitals.get('resting_hr_bpm_night_mean')}。")
                print(f"✅ 用户 {user_id} 基础数据与历史体征注入完成！")
    except Exception as e:
        print(f"加载 dataset 报错: {e}")

    # 2. 注入那个极具价值的 10天连贯数据集！给它一个专门的 user_id
    try:
        TEN_DAYS_USER = "stress_non_dipper_10days_user"
        project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{TEN_DAYS_USER}")
        memory = project.memory(group_id="default", agent_id="health_bot", user_id=TEN_DAYS_USER,
                                session_id="init_session")

        with open("data/sft_stress_single_user_10days.json", "r", encoding="utf-8") as f:
            ten_days_data = json.load(f)

            # 第一天的画像作为基线注入
            base_traits = ten_days_data[0]["input_context"]["user_traits"]
            memory.add(
                f"【基本画像】年龄{base_traits['age_years']}岁，性别{base_traits['sex']}，BMI {base_traits['bmi']}。血压倾向：{base_traits.get('bp_phenotype_hint')}")

            # 严格按时间序列注入连续 10 天的体征
            for day_data in ten_days_data:
                sensor = day_data["input_context"]["sensor_data_short_term"]
                day = day_data.get("day", "Day 1")
                day_formatted = day.replace("Day ", "Day 0") if len(day) == 5 else day

                sleep = sensor.get("sleep", {})
                vitals = sensor.get("vitals_summary", {})
                memory.add(
                    f"[{day_formatted}] 历史传感器记录：睡眠{sleep.get('total_sleep_hours')}h，起夜{sleep.get('awakenings_count')}次。日间心率{vitals.get('resting_hr_bpm_day_mean')}，夜间心率{vitals.get('resting_hr_bpm_night_mean')}。")
        print(f"✅ 10天连续演变用户 ({TEN_DAYS_USER}) 时序数据注入完成！")
    except Exception as e:
        print(f"加载 10days 数据集报错: {e}")


if __name__ == "__main__":
    init_database()