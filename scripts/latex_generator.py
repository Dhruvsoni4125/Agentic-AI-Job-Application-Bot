import json
import os
import shutil
import subprocess

# ==========================================
# PATHS
# ==========================================

TEMPLATE_FILE = "templates/resume_template.tex"
CLASS_FILE = "templates/resume.cls"

INPUT_DIR = "outputs/ats_resumes"
TEX_DIR = "outputs/ats_resume_tex"
PDF_DIR = "outputs/ats_resume_pdf"

PDFLATEX_PATH = r"C:\Users\Dhruv\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
if not os.path.exists(PDFLATEX_PATH):
    PDFLATEX_PATH = shutil.which("pdflatex")

os.makedirs(TEX_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# ==========================================
# LATEX ESCAPE
# ==========================================

def latex_escape(text):
    if text is None:
        return ""

    text = str(text)

    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


# ==========================================
# EDUCATION
# ==========================================

def build_education(data):
    degree = latex_escape(
        data["education"]["degree"]
    )

    institution = latex_escape(
        data["education"]["institution"]
    )

    cgpa = data["education"]["cgpa"]

    return (
        f"{{\\bf {degree}}}\\\\\n"
        f"{institution} \\hfill "
        f"{{CGPA: {cgpa}}}"
    )


# ==========================================
# SKILLS
# ==========================================

def build_skills(data):

    rows = []

    for category, skills in data["skills"].items():

        if not skills:
            continue

        skill_text = ", ".join(
            latex_escape(skill)
            for skill in skills
        )

        rows.append(
            f"{latex_escape(category)} & "
            f"{skill_text}\\\\"
        )

    table = (
        "\\begin{tabular}"
        "{ @{} >{\\bfseries}l "
        "@{\\hspace{6ex}} l }\n"
    )

    table += "\n".join(rows)

    table += "\n\\end{tabular}"

    return table


# ==========================================
# EXPERIENCE
# ==========================================

def build_experience(data):

    output = ""

    for exp in data["experience"]:

        output += (
            f"\\textbf{{{latex_escape(exp['title'])}}}"
            f" \\hfill "
            f"{{{latex_escape(exp['duration'])}}}\\\\\n"
        )

        output += (
            f"\\textit{{{latex_escape(exp['company'])}}}\n"
        )

        output += "\\begin{itemize}\n"

        for bullet in exp["bullets"]:

            output += (
                f"\\item "
                f"{latex_escape(bullet)}\n"
            )

        output += "\\end{itemize}\n\n"

    return output


# ==========================================
# PROJECTS
# ==========================================

def build_projects(data):

    output = ""

    for project in data["projects"]:

        output += (
            f"\\textbf{{{latex_escape(project['name'])}}}\n"
        )

        output += "\\begin{itemize}\n"

        for bullet in project["bullets"]:

            output += (
                f"\\item "
                f"{latex_escape(bullet)}\n"
            )

        output += "\\end{itemize}\n\n"

    return output


# ==========================================
# LOAD LATEX TEMPLATE
# ==========================================

with open(
    TEMPLATE_FILE,
    "r",
    encoding="utf-8"
) as f:

    template = f.read()


# ==========================================
# PROCESS ALL JSON RESUMES
# ==========================================

for file_name in os.listdir(INPUT_DIR):

    if not file_name.endswith(".json"):
        continue

    print(f"\nGenerating Resume: {file_name}")

    json_path = os.path.join(
        INPUT_DIR,
        file_name
    )

    with open(
        json_path,
        "r",
        encoding="utf-8"
    ) as f:

        resume = json.load(f)

    tex_content = template

    tex_content = tex_content.replace(
        "{{SUMMARY}}",
        latex_escape(resume["summary"])
    )

    tex_content = tex_content.replace(
        "{{EDUCATION}}",
        build_education(resume)
    )

    tex_content = tex_content.replace(
        "{{SKILLS}}",
        build_skills(resume)
    )

    tex_content = tex_content.replace(
        "{{EXPERIENCE}}",
        build_experience(resume)
    )

    tex_content = tex_content.replace(
        "{{PROJECTS}}",
        build_projects(resume)
    )

    base_name = os.path.splitext(
        file_name
    )[0]

    tex_file = os.path.join(
        TEX_DIR,
        f"{base_name}.tex"
    )

    with open(
        tex_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(tex_content)

    shutil.copy(
        CLASS_FILE,
        os.path.join(
            TEX_DIR,
            "resume.cls"
        )
    )

    print(f"TEX Generated: {base_name}.tex")

    try:

        if not PDFLATEX_PATH:
            print(f"PDF Compilation Skipped: pdflatex not found for {base_name}")
            continue

        subprocess.run(
            [
                PDFLATEX_PATH,
                "-interaction=nonstopmode",
                f"{base_name}.tex"
            ],
            cwd=TEX_DIR,
            check=True
        )

        generated_pdf = os.path.join(
            TEX_DIR,
            f"{base_name}.pdf"
        )

        if os.path.exists(generated_pdf):

            shutil.copy(
                generated_pdf,
                os.path.join(
                    PDF_DIR,
                    f"{base_name}.pdf"
                )
            )

            print(
                f"PDF Generated: {base_name}.pdf"
            )

    except (subprocess.CalledProcessError, FileNotFoundError):

        print(
            f"PDF Compilation Failed: {base_name}"
        )

print("\n===================================")
print("ALL PDF RESUMES GENERATED")
print("===================================")
