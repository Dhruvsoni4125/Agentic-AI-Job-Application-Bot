# app/services/pdf_generator.py
import asyncio
import logging
from jinja2 import Template
# WeasyPrint is imported lazily in generate_pdf_sync() because it requires
# GTK/Pango system libraries that may not be available on all dev machines (e.g., Windows).

logger = logging.getLogger(__name__)

# Classic / ATS-safe template (highly structured, plain text, easy for parsers)
CLASSIC_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {
        size: A4;
        margin: 20mm;
    }
    body {
        font-family: "Times New Roman", Times, serif;
        font-size: 11pt;
        line-height: 1.4;
        color: #333333;
        margin: 0;
        padding: 0;
    }
    h1 {
        font-size: 20pt;
        text-align: center;
        margin: 0 0 5px 0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .contact-info {
        text-align: center;
        font-size: 9.5pt;
        margin-bottom: 20px;
        border-bottom: 1px solid #000;
        padding-bottom: 8px;
    }
    .contact-info span {
        margin: 0 8px;
    }
    .section-title {
        font-size: 12pt;
        font-weight: bold;
        text-transform: uppercase;
        border-bottom: 1px solid #000;
        margin-top: 15px;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }
    .summary {
        margin-bottom: 12px;
        text-align: justify;
    }
    .item {
        margin-bottom: 10px;
    }
    .item-header {
        font-weight: bold;
        display: flex;
        justify-content: space-between;
    }
    .item-subheader {
        font-style: italic;
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    ul {
        margin: 3px 0;
        padding-left: 20px;
    }
    li {
        margin-bottom: 3px;
        text-align: justify;
    }
    .skills-list {
        margin-bottom: 10px;
    }
    .skills-category {
        font-weight: bold;
    }
</style>
</head>
<body>
    <h1>{{ name }}</h1>
    <div class="contact-info">
        {% if email %}<span>Email: {{ email }}</span>|{% endif %}
        {% if phone %}<span>Phone: {{ phone }}</span>|{% endif %}
        {% if linkedin %}<span>LinkedIn: {{ linkedin }}</span>|{% endif %}
        {% if github %}<span>GitHub: {{ github }}</span>|{% endif %}
        {% if location %}<span>{{ location }}</span>{% endif %}
    </div>

    {% if summary %}
    <div class="section-title">Professional Summary</div>
    <div class="summary">
        {{ summary }}
    </div>
    {% endif %}

    {% if experience %}
    <div class="section-title">Professional Experience</div>
    {% for job in experience %}
    <div class="item">
        <div class="item-header">
            <span>{{ job.role }}</span>
            <span>{{ job.duration }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ job.company }}</span>
            <span>{{ job.location }}</span>
        </div>
        <ul>
            {% for bullet in job.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}

    {% if education %}
    <div class="section-title">Education</div>
    {% for edu in education %}
    <div class="item">
        <div class="item-header">
            <span>{{ edu.degree }}</span>
            <span>{{ edu.year }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ edu.school }}</span>
            <span>{{ edu.grade }}</span>
        </div>
    </div>
    {% endfor %}
    {% endif %}

    {% if skills %}
    <div class="section-title">Skills</div>
    <div class="skills-list">
        {% if skills is mapping %}
            {% for category, items in skills.items() %}
            <div><span class="skills-category">{{ category }}:</span> {{ items|join(', ') }}</div>
            {% endfor %}
        {% else %}
            <div>{{ skills|join(', ') }}</div>
        {% endif %}
    </div>
    {% endif %}

    {% if projects %}
    <div class="section-title">Key Projects</div>
    {% for proj in projects %}
    <div class="item">
        <div class="item-header">
            <span>{{ proj.title }}</span>
            {% if proj.tech %}<span>{{ proj.tech|join(', ') }}</span>{% endif %}
        </div>
        <ul>
            {% for bullet in proj.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}
</body>
</html>
"""

# Modern template (Clean, typography-focused with subtle styling)
MODERN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {
        size: A4;
        margin: 18mm;
    }
    body {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.5;
        color: #2c3e50;
        margin: 0;
        padding: 0;
    }
    header {
        border-bottom: 2px solid #3498db;
        padding-bottom: 12px;
        margin-bottom: 15px;
    }
    h1 {
        font-size: 22pt;
        color: #2c3e50;
        margin: 0 0 5px 0;
        font-weight: 300;
        letter-spacing: 0.5px;
    }
    .contact-info {
        font-size: 8.5pt;
        color: #7f8c8d;
        display: flex;
        flex-wrap: wrap;
    }
    .contact-info span {
        margin-right: 15px;
    }
    .section-title {
        font-size: 11pt;
        font-weight: bold;
        color: #3498db;
        text-transform: uppercase;
        margin-top: 18px;
        margin-bottom: 8px;
        letter-spacing: 1px;
    }
    .summary {
        margin-bottom: 12px;
        color: #34495e;
    }
    .item {
        margin-bottom: 12px;
    }
    .item-header {
        font-weight: 600;
        color: #2c3e50;
        display: flex;
        justify-content: space-between;
    }
    .item-subheader {
        color: #7f8c8d;
        font-size: 9pt;
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    ul {
        margin: 3px 0;
        padding-left: 15px;
    }
    li {
        margin-bottom: 4px;
        color: #34495e;
    }
    .skills-container {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .skills-row {
        font-size: 9.5pt;
    }
    .skills-category {
        font-weight: bold;
        color: #2c3e50;
    }
</style>
</head>
<body>
    <header>
        <h1>{{ name }}</h1>
        <div class="contact-info">
            {% if email %}<span>✉ {{ email }}</span>{% endif %}
            {% if phone %}<span>📞 {{ phone }}</span>{% endif %}
            {% if linkedin %}<span>🔗 {{ linkedin }}</span>{% endif %}
            {% if github %}<span>🐙 {{ github }}</span>{% endif %}
            {% if location %}<span>📍 {{ location }}</span>{% endif %}
        </div>
    </header>

    {% if summary %}
    <div class="section-title">Summary</div>
    <div class="summary">
        {{ summary }}
    </div>
    {% endif %}

    {% if experience %}
    <div class="section-title">Experience</div>
    {% for job in experience %}
    <div class="item">
        <div class="item-header">
            <span>{{ job.role }}</span>
            <span style="font-weight: normal; color: #7f8c8d;">{{ job.duration }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ job.company }}</span>
            <span>{{ job.location }}</span>
        </div>
        <ul>
            {% for bullet in job.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}

    {% if education %}
    <div class="section-title">Education</div>
    {% for edu in education %}
    <div class="item">
        <div class="item-header">
            <span>{{ edu.degree }}</span>
            <span style="font-weight: normal; color: #7f8c8d;">{{ edu.year }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ edu.school }}</span>
            <span>{{ edu.grade }}</span>
        </div>
    </div>
    {% endfor %}
    {% endif %}

    {% if skills %}
    <div class="section-title">Skills</div>
    <div class="skills-container">
        {% if skills is mapping %}
            {% for category, items in skills.items() %}
            <div class="skills-row"><span class="skills-category">{{ category }}:</span> {{ items|join(', ') }}</div>
            {% endfor %}
        {% else %}
            <div class="skills-row">{{ skills|join(', ') }}</div>
        {% endif %}
    </div>
    {% endif %}

    {% if projects %}
    <div class="section-title">Projects</div>
    {% for proj in projects %}
    <div class="item">
        <div class="item-header">
            <span>{{ proj.title }}</span>
            {% if proj.tech %}<span style="font-weight: normal; color: #7f8c8d;">{{ proj.tech|join(', ') }}</span>{% endif %}
        </div>
        <ul>
            {% for bullet in proj.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}
</body>
</html>
"""

# Creative / Bold template (vibrant, modern, with accent sidebar)
CREATIVE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {
        size: A4;
        margin: 15mm;
    }
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 10pt;
        line-height: 1.5;
        color: #1a1a2e;
        margin: 0;
        padding: 0;
    }
    header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px 20px;
        margin: -15mm -15mm 15px -15mm;
        border-radius: 0 0 8px 8px;
    }
    h1 {
        font-size: 24pt;
        font-weight: 700;
        margin: 0 0 8px 0;
        letter-spacing: 0.5px;
    }
    .contact-info {
        font-size: 8.5pt;
        opacity: 0.9;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
    }
    .section-title {
        font-size: 12pt;
        font-weight: 700;
        color: #667eea;
        text-transform: uppercase;
        margin-top: 18px;
        margin-bottom: 8px;
        letter-spacing: 1.5px;
        border-left: 4px solid #764ba2;
        padding-left: 10px;
    }
    .summary {
        margin-bottom: 12px;
        color: #333;
        padding: 10px;
        background: #f8f9ff;
        border-radius: 6px;
    }
    .item {
        margin-bottom: 12px;
        padding-left: 10px;
        border-left: 2px solid #e8e8e8;
    }
    .item-header {
        font-weight: 600;
        color: #1a1a2e;
        display: flex;
        justify-content: space-between;
    }
    .item-subheader {
        color: #666;
        font-size: 9pt;
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    ul {
        margin: 3px 0;
        padding-left: 15px;
    }
    li {
        margin-bottom: 4px;
        color: #333;
    }
    .skills-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }
    .skill-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 8.5pt;
        font-weight: 500;
    }
    .project-tech {
        color: #764ba2;
        font-size: 8.5pt;
        font-weight: 500;
    }
</style>
</head>
<body>
    <header>
        <h1>{{ name }}</h1>
        <div class="contact-info">
            {% if email %}<span>✉ {{ email }}</span>{% endif %}
            {% if phone %}<span>📞 {{ phone }}</span>{% endif %}
            {% if linkedin %}<span>🔗 {{ linkedin }}</span>{% endif %}
            {% if github %}<span>🐙 {{ github }}</span>{% endif %}
            {% if location %}<span>📍 {{ location }}</span>{% endif %}
        </div>
    </header>

    {% if summary %}
    <div class="section-title">About Me</div>
    <div class="summary">
        {{ summary }}
    </div>
    {% endif %}

    {% if experience %}
    <div class="section-title">Experience</div>
    {% for job in experience %}
    <div class="item">
        <div class="item-header">
            <span>{{ job.role }}</span>
            <span style="font-weight: normal; color: #764ba2;">{{ job.duration }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ job.company }}</span>
            <span>{{ job.location }}</span>
        </div>
        <ul>
            {% for bullet in job.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}

    {% if skills %}
    <div class="section-title">Skills</div>
    <div class="skills-grid">
        {% if skills is mapping %}
            {% for category, items in skills.items() %}
                {% for item in items %}
                <span class="skill-tag">{{ item }}</span>
                {% endfor %}
            {% endfor %}
        {% else %}
            {% for skill in skills %}
            <span class="skill-tag">{{ skill }}</span>
            {% endfor %}
        {% endif %}
    </div>
    {% endif %}

    {% if education %}
    <div class="section-title">Education</div>
    {% for edu in education %}
    <div class="item">
        <div class="item-header">
            <span>{{ edu.degree }}</span>
            <span style="font-weight: normal; color: #764ba2;">{{ edu.year }}</span>
        </div>
        <div class="item-subheader">
            <span>{{ edu.school }}</span>
            <span>{{ edu.grade }}</span>
        </div>
    </div>
    {% endfor %}
    {% endif %}

    {% if projects %}
    <div class="section-title">Projects</div>
    {% for proj in projects %}
    <div class="item">
        <div class="item-header">
            <span>{{ proj.title }}</span>
            {% if proj.tech %}<span class="project-tech">{{ proj.tech|join(', ') }}</span>{% endif %}
        </div>
        <ul>
            {% for bullet in proj.description %}
            <li>{{ bullet }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
    {% endif %}
</body>
</html>
"""

TEMPLATES = {
    "classic": CLASSIC_TEMPLATE,
    "modern": MODERN_TEMPLATE,
    "creative": CREATIVE_TEMPLATE
}

async def generate_resume_pdf(data: dict, template_name: str = "classic", output_path: str = None) -> bytes:
    """
    Asynchronously generates a resume PDF from data using Playwright (Chromium).
    Honors @page CSS margins and layouts.
    """
    from playwright.async_api import async_playwright
    try:
        logger.info(f"Rendering HTML template '{template_name}' to PDF via Playwright...")
        template_str = TEMPLATES.get(template_name, CLASSIC_TEMPLATE)
        template = Template(template_str)
        html_content = template.render(**data)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content)
            # Wait for layouts to settle
            await page.evaluate("document.fonts.ready")
            
            # Generate PDF matching WeasyPrint's A4 format
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True
            )
            await browser.close()
            
        if output_path:
            await asyncio.to_thread(lambda: open(output_path, "wb").write(pdf_bytes))
            
        logger.info("PDF generation complete.")
        return pdf_bytes
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise
