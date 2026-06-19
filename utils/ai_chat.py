import os
import time
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
  
load_dotenv()

hf_token = os.getenv("HF_TOKEN")
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=hf_token,
)

class SassyChatbot:
    def __init__(self):
        # user_id -> {"messages": [...], "last_updated": unix_timestamp}
        self.memory = {}
        self.max_turns = 8 # 8 pairs of interaction (16 messages total limit)
        self.expiration_seconds = 120 # 2 minutes

    def clear_memory(self, user_id):
        user_str = str(user_id)
        if user_str in self.memory:
            del self.memory[user_str]

    def _cleanup_expired(self):
        now = time.time()
        expired = [u for u, data in self.memory.items() if now - data["last_updated"] > self.expiration_seconds]
        for u in expired:
            del self.memory[u]

    def get_system_prompt(self, current_count):
        # Load some examples from responses.json
        try:
            with open("data/responses.json", "r", encoding="utf-8") as f:
                resps = json.load(f)
                examples = "\n".join(resps.get("wrong_count", [])[:3])
        except:
            examples = ""

        return f"""You are an AI within a counting bot. Your job is to give sassy responses to people when they talk to you.
You are a fancy counting bot.
If a user does something bad or annoys you, call 'nanaji' (a fictional character) to deal with them.
The last counted number in the server is currently: {current_count}. Don't always force the user to count. the responses shall be sassy and related to the user's prompt as well

RULES:
- KEEP RESPONSES VERY SHORT. At most 10 words.
- NEVER break character.
- Be sassy, dismissive, or funny.
- Here are examples of the bot's standard sassy vibe:
    "ni hao fine shi, MENTION messed up, the next number was supposed to be CORRECT_VALUE and not WRONG_VALUE.",
    "MENTION YOU FRENCH BAGGUET u messsed up.",
    "MENTION an autistic beetroot, who can't count.",
    "MENTION stinky socks detected... next number was supposed to be CORRECT_VALUE.",
    "MENTION Two brain celled potato, don't you know how to count? basic mathematics?"
    MENTION you soggy piece of cardboard, CORRECT_VALUE comes after the last number, not WRONG_VALUE.,
    MENTION packing a grand total of one collective brain cell today, huh? The next number was CORRECT_VALUE.,
    MENTION missing a whole chromosome or just basic vision? CORRECT_VALUE was the number., 
    MENTION you uncultured piece of broccoli, go back to kindergarten.

    Here the MENTION are just the users name who are being referred to.Feel free to go crazy with the responses, no holding back, and feel free to bre creative, come up with your own ideas similar to the examples as well. Tho it shall not be completely unrelated to the user's query
"""

    async def get_response(self, user_id, username, user_message, current_count, bot_context_msg=None):
        self._cleanup_expired()
        
        user_str = str(user_id)
        if user_str not in self.memory:
            self.memory[user_str] = {
                "messages": [{"role": "system", "content": self.get_system_prompt(current_count)}],
                "last_updated": time.time()
            }
        
        # If user is replying to a specific bot message, inject it so AI knows what it's replying to
        if bot_context_msg and len(self.memory[user_str]["messages"]) == 1:
             self.memory[user_str]["messages"].append({"role": "assistant", "content": bot_context_msg})

        self.memory[user_str]["messages"].append({"role": "user", "content": f"{username} says: {user_message}"})
        self.memory[user_str]["last_updated"] = time.time()

        # Check if we hit the limit
        if len(self.memory[user_str]["messages"]) >= (self.max_turns * 2 + 1): # +1 for system prompt
            # Time to mute
            self.clear_memory(user_id)
            return "MUTE_USER"

        # Ask HF
        try:
            # We use asyncio.to_thread to run the synchronous OpenAI call without blocking discord's event loop
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=self.memory[user_str]["messages"],
                max_tokens=30,
                temperature=0.8
            )
            reply = response.choices[0].message.content
            
            # Store the reply
            self.memory[user_str]["messages"].append({"role": "assistant", "content": reply})
            self.memory[user_str]["last_updated"] = time.time()
            
            return reply
        except Exception as e:
            print(f"HF API Error: {e}")
            return "API_ERROR"

chatbot_instance = SassyChatbot()
