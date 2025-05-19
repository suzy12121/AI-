from flask import Flask, request, render_template
from openai import OpenAI
import fitz
import os
import datetime
import json
import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Google Sheets setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

service_account_info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
gc = gspread.authorize(creds)

@app.route('/')
def index():
    return render_template('index.html')

def parse_mcqs_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    questions = []
    for block in soup.find_all('div', class_='mcq'):
        q = {}
        q_text = block.find('h3')
        q['問題'] = q_text.text.replace('問題：', '').strip() if q_text else ''
        options = block.find_all('li')
        for opt in options:
            label = opt.text.strip()[0]
            q[label] = opt.text.strip()[2:].strip()
        answer_tag = block.find('p')
        if answer_tag:
            q['答案'] = answer_tag.text.replace('答案：', '').strip()
        if len(q) == 6:
            questions.append(q)
    return questions

def write_questions_to_new_sheet(questions, title_prefix="AI題庫"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    spreadsheet_title = f"{title_prefix} - {timestamp}"
    sh = gc.create(spreadsheet_title)
    worksheet = sh.sheet1
    worksheet.update("A1:F1", [["問題", "A", "B", "C", "D", "答案"]])
    rows = [[q["問題"], q["A"], q["B"], q["C"], q["D"], q["答案"]] for q in questions]
    worksheet.update(f"A2:F{len(rows)+1}", rows)
    return f"https://docs.google.com/spreadsheets/d/{sh.id}"

@app.route('/upload', methods=['POST'])
def upload():
    try:
        print("🚀 Upload started")

        pdf_file = request.files['pdf']
        print("📄 PDF received:", pdf_file.filename)

        text = ""
        with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()

        input_text = text[:3000]
        print("✂️ Extracted text:", input_text[:100])  # Preview for debugging

        prompt = f"""
根據以下繁體中文內容，請生成三題選擇題，並用 HTML 格式輸出，具備良好排版與縮排，格式如下：

<div class="mcq">
  <h3>問題：____</h3>
  <ul>
    <li><strong>A:</strong> ____</li>
    <li><strong>B:</strong> ____</li>
    <li><strong>C:</strong> ____</li>
    <li><strong>D:</strong> ____</li>
  </ul>
  <p><strong>答案：</strong> __</p>
</div>

請不要加入說明文字或其他 HTML 元素。以下是內容：
{input_text}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        generated_html = response.choices[0].message.content
        print("✅ GPT Response OK")

        questions = parse_mcqs_from_html(generated_html)
        print("🧠 Parsed questions:", questions)

        sheet_url = write_questions_to_new_sheet(questions)
        print("📤 Sheet created at:", sheet_url)

        return render_template("index.html", mcqs=generated_html, sheet_url=sheet_url, error=None)

    except Exception as e:
        print("❌ Exception occurred:", str(e))
        return render_template("index.html", mcqs=None, sheet_url=None, error=str(e))



        prompt = f"""
根據以下繁體中文內容，請生成三題選擇題，並用 HTML 格式輸出，具備良好排版與縮排，格式如下：

<div class="mcq">
  <h3>問題：____</h3>
  <ul>
    <li><strong>A:</strong> ____</li>
    <li><strong>B:</strong> ____</li>
    <li><strong>C:</strong> ____</li>
    <li><strong>D:</strong> ____</li>
  </ul>
  <p><strong>答案：</strong> __</p>
</div>

請不要加入說明文字或其他 HTML 元素。以下是內容：
{input_text}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        generated_html = response.choices[0].message.content
        questions = parse_mcqs_from_html(generated_html)
        sheet_url = write_questions_to_new_sheet(questions)

        return render_template("index.html", mcqs=generated_html, sheet_url=sheet_url, error=None)

    except Exception as e:
        return render_template("index.html", mcqs=None, sheet_url=None, error=str(e))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
