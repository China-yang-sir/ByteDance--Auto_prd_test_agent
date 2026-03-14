import os
import json


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CONFIG_FILE = os.path.join(DATA_DIR, 'user_config.json')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_config():
    config = {}
    env_key = os.environ.get("QWEN_API_KEY")
    if env_key:
        config['api_key'] = env_key
    return config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"保存配置失败: {e}")