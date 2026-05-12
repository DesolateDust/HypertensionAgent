import json
from memmachine_client import MemMachineClient
from cache_manager import process_and_cache_sensor_data, save_cache  # 引入我们的模块


def safe_get(dictionary, key, suffix=""):
    if dictionary is None: return "未知"
    val = dictionary.get(key)
    return f"{val}{suffix}" if val is not None else "未知"


def init_database():
    # 每次初始化前清空旧缓存
    save_cache({})
    client = MemMachineClient(base_url="http://localhost:8080")
    print("开始初始化底层数据库与热缓存...")

    # ==========================================
    # 1. 恢复多用户单日数据集 (为了演示切换用户)
    # ==========================================
    try:
        with open("data/sft_dataset.json", "r", encoding="utf-8") as f:
            datasets = json.load(f)
            for data in datasets:
                user_id = data.get("user_id", "unknown_user")
                project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{user_id}")
                memory = project.memory(group_id="default", agent_id="health_bot", user_id=user_id,
                                        session_id="init_session")

                # 注入画像(冷库)
                traits = data["input_context"]["user_traits"]
                memory.add(
                    f"【基本画像】年龄{traits['age_years']}岁，性别{traits['sex']}，BMI {traits['bmi']}。血压表型倾向：{traits.get('bp_phenotype_hint', '未知')}")

                # 注入单日传感器数据(走热缓存引擎！)
                if "sensor_data_short_term" in data["input_context"]:
                    sensor = data["input_context"]["sensor_data_short_term"] or {}
                    slp_hrs = safe_get(sensor.get("sleep", {}), 'total_sleep_hours', 'h')
                    awake = safe_get(sensor.get("sleep", {}), 'awakenings_count', '次')
                    day_hr = safe_get(sensor.get("vitals_summary", {}), 'resting_hr_bpm_day_mean')
                    night_hr = safe_get(sensor.get("vitals_summary", {}), 'resting_hr_bpm_night_mean')

                    content = f"【Day 1】睡眠{slp_hrs}，起夜{awake}。日间心率{day_hr}，夜间心率{night_hr}。"
                    process_and_cache_sensor_data(user_id, 1, content, memory)

                print(f"✅ 普通用户 {user_id} 基础数据与热缓存注入完成！")
    except Exception as e:
        print(f"加载 dataset 报错: {e}")

    # ==========================================
    # 2. 注入 10 天连续数据集 (自动验证触发逻辑！)
    # ==========================================
    try:
        TEN_DAYS_USER = "stress_non_dipper_10days_user"
        project = client.get_or_create_project(org_id="edge_device", project_id=f"health_db_{TEN_DAYS_USER}")
        memory = project.memory(group_id="default", agent_id="health_bot", user_id=TEN_DAYS_USER,
                                session_id="init_session")

        with open("data/sft_stress_single_user_10days.json", "r", encoding="utf-8") as f:
            ten_days_data = json.load(f)

            base_traits = ten_days_data[0]["input_context"]["user_traits"]
            memory.add(
                f"【基本画像】年龄{base_traits['age_years']}岁，性别{base_traits['sex']}，BMI {base_traits['bmi']}。血压倾向：{base_traits.get('bp_phenotype_hint')}")

            print(f"\n--- 开始注入 10 天用户数据，请观察压缩触发情况 ---")
            for i, day_data in enumerate(ten_days_data):
                day_num = i + 1
                sensor = day_data["input_context"].get("sensor_data_short_term", {}) or {}

                slp_hrs = safe_get(sensor.get("sleep", {}), 'total_sleep_hours', 'h')
                awake = safe_get(sensor.get("sleep", {}), 'awakenings_count', '次')
                day_hr = safe_get(sensor.get("vitals_summary", {}), 'resting_hr_bpm_day_mean')
                night_hr = safe_get(sensor.get("vitals_summary", {}), 'resting_hr_bpm_night_mean')

                content = f"【Day {day_num}】睡眠{slp_hrs}，起夜{awake}。日间心率{day_hr}，夜间心率{night_hr}。"
                # 这里调用相同的处理逻辑，当注入到 Day 8 时，会自动弹出 Day 1 并触发总结！
                process_and_cache_sensor_data(TEN_DAYS_USER, day_num, content, memory)

        print(f"✅ 10天测试用户 ({TEN_DAYS_USER}) 初始化完成！")
    except Exception as e:
        print(f"加载 10days 报错: {e}")


if __name__ == "__main__":
    init_database()