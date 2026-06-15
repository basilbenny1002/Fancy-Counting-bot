import json

with open('data/responses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['fell_for_troll'] = [
    "{MENTION} haha bro fell for it, that was a troll! Next number is 1.",
    "{MENTION} you actually fell for the troll 😂 Next number is 1.",
    "{MENTION} caught in 4k falling for the troll 📸 Next number is 1."
]

with open('data/responses.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
