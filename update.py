import json

with open('data/responses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['wrong_count'] = [
    "ni hao fine shi, {MENTION} messed up, the next number was supposed to be {CORRECT_VALUE} and not {WRONG_VALUE}. Back to the beginning, next number is 1!",
    "{MENTION} YOU FRENCH BAGGUET u messsed up. We're starting over from 1.",
    "{MENTION} an autistic beetroot, who can't count. Next number is 1 again.",
    "{MENTION} stinky socks detected... next number was supposed to be {CORRECT_VALUE}. Resetting back to 1!",
    "{MENTION} Two brain celled potato, don't you know how to count? basic mathematics? Next number is 1.",
    "¡sɔıʇɐɯǝɥʇɐɯ ɔısɐq ¿ʇunoɔ oʇ ʍoɥ ʍouʞ noʎ ʇ,uop 'oʇɐʇod pǝllǝɔ uıɐɹq oʍ⊥ {MENTION} sdn pǝssǝɯ. 1 oʇ ʞɔɐq",
    "你算错了 {MENTION}, 下一个数字是 {CORRECT_VALUE} (You counted wrong, next number is {CORRECT_VALUE}). We are restarting from 1."
]

with open('data/responses.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
