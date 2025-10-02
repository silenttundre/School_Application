import os
from flask import Flask, render_template, request, redirect, url_for
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()
# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Initialize LLM
llm = ChatGllm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)

# Prompt for generating sentence pairs
GEN_PROMPT = """
Create 10 pairs of simple sentences suitable for 6th graders. 
Each pair should be able to be combined into one precise sentence.
Format them as a numbered list:
1) sentence A. sentence B.
2) ...
"""

# Prompt for grading student answers
GRADE_PROMPT = """
You are grading a 6th grade sentence-combining exercise. 
You will be given:
- Two original sentences
- A student's combined sentence

Your job:
1. Check if the student’s sentence is grammatically correct and precise.
2. If correct: say "✅ Correct".
3. If incorrect: say "❌ Incorrect", then show:
   - A corrected version of the combined sentence.
   - A brief explanation of what was wrong.

Format:
Result: [✅/❌]
Correct Answer: [...]
Explanation: [...]
"""

def generate_sentence_pairs():
    response = llm.invoke(GEN_PROMPT)
    text = response.content.strip()

    # Only keep lines starting with a number and a parenthesis
    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip().startswith(tuple(str(i) for i in range(1, 11)))
    ]
    return lines


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/quiz")
def quiz():
    pairs = generate_sentence_pairs()
    return render_template("quiz.html", pairs=pairs)

@app.route("/submit", methods=["POST"])
def submit():
    pairs = request.form.getlist("pair")
    answers = request.form.getlist("answer")

    feedback = []
    score = 0

    for pair, ans in zip(pairs, answers):
        prompt = f"""
        Original sentences: {pair}
        Student answer: {ans}
        {GRADE_PROMPT}
        """
        result = llm.invoke(prompt).content

        # count correct answers
        if "✅" in result:
            score += 1

        feedback.append({"pair": pair, "student": ans, "feedback": result})

    total = len(pairs)
    return render_template("results.html", feedback=feedback, score=score, total=total)

@app.route("/retry")
def retry():
    return redirect(url_for("quiz"))

if __name__ == "__main__":
    app.run(debug=True)
