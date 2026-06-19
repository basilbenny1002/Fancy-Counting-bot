import json

with open('data/responses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['ai_timeout'] = [
    "{MENTION} we're here to count, not yap. so now count. muting myself for 1 hr"
]
data['muted_random_reply'] = [
    "{MENTION} 🤐 (I'm ignoring you)",
    "{MENTION} 🤫 shhh, I'm muted.",
    "{MENTION} talk to the hand, I'm in timeout.",
    "{MENTION} 💤"
]
data['muted_spam_reply'] = [
    "{MENTION} I said I'm muted for an hour! We're here to count! Bot still in timeout for u."
]
data['ai_error'] = [
    "{MENTION} developer ran out of free tiers :\"D and too broke to pay fro ai so no more yappign till teh end of the month"
]

with open('data/responses.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
