import json

with open("outputs/resume.json", "r", encoding="utf-8") as f:
    resume = json.load(f)

skills = resume["skills"]

keywords = [
    "Generative AI Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "LLM Engineer",
    "Python Developer",
    "Data Scientist",
    "AI Intern",
    "Machine Learning Intern"
]

print(keywords)