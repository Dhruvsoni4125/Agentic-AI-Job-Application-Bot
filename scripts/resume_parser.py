import json

from utils import chat_completion, extract_json, project_path, write_json


PDF_PATH = project_path("data", "Dhruv_Resume.pdf")
OUTPUT_PATH = project_path("outputs", "resume.json")


def extract_resume_text(pdf_path):
    try:
        import fitz

        doc = fitz.open(pdf_path)
        return "".join(page.get_text() for page in doc)

    except ModuleNotFoundError:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


resume_text = extract_resume_text(PDF_PATH)

prompt = f"""
Extract the resume information and return ONLY valid JSON.

Required format:

{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": [],
  "education": [],
  "experience": [],
  "projects": []
}}

Resume:

{resume_text}
"""

try:
    result = chat_completion(prompt, temperature=0)
    parsed_json = extract_json(result)
    write_json(OUTPUT_PATH, parsed_json)

    print("resume.json created successfully")
    print(json.dumps(parsed_json, indent=4))

except Exception as e:
    print(f"Error: {e}")
    raise
