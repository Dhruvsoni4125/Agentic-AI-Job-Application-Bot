import json

with open("outputs/resume.json", "r", encoding="utf-8") as f:
    resume = json.load(f)

skills = resume["skills"]

print(skills)