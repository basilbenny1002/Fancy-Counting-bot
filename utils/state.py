import json
import os

STATE_FILE = "data/state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def get_guild_state(guild_id):
    state = load_state()
    guild_id_str = str(guild_id)
    if guild_id_str not in state:
        state[guild_id_str] = {
            "channel_id": None,
            "current_count": 0,
            "last_user_id": None,
            "allow_consecutive": False
        }
    return state[guild_id_str]

def update_guild_state(guild_id, **kwargs):
    state = load_state()
    guild_id_str = str(guild_id)
    if guild_id_str not in state:
        state[guild_id_str] = {
            "channel_id": None,
            "current_count": 0,
            "last_user_id": None,
            "allow_consecutive": False
        }
    for k, v in kwargs.items():
        state[guild_id_str][k] = v
    save_state(state)
