import json
import os
import time

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

def get_muted_user(user_id):
    state = load_state()
    if "muted_users" not in state:
        state["muted_users"] = {}
        
    user_str = str(user_id)
    user_data = state["muted_users"].get(user_str)
    
    if user_data:
        # Check if timeout expired
        if time.time() > user_data.get("muted_until", 0):
            # Expired, delete the user details as requested
            del state["muted_users"][user_str]
            save_state(state)
            return None
        return user_data
    return None

def update_muted_user(user_id, muted_until=None, ping_count=None):
    state = load_state()
    if "muted_users" not in state:
        state["muted_users"] = {}
        
    user_str = str(user_id)
    if user_str not in state["muted_users"]:
        state["muted_users"][user_str] = {"muted_until": 0, "ping_count": 0}
        
    if muted_until is not None:
        state["muted_users"][user_str]["muted_until"] = muted_until
    if ping_count is not None:
        state["muted_users"][user_str]["ping_count"] = ping_count
        
    save_state(state)
