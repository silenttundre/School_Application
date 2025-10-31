import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import json

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'replace-this-with-a-secure-secret'

COMMON_PREFIXES = {
    'un': 'not, opposite of',
    're': 'again, back',
    'pre': 'before',
    'in': 'not',
    'im': 'not',
    'dis': 'not, opposite of',
    'mis': 'wrongly',
    'non': 'not',
    'sub': 'under'
}
COMMON_SUFFIXES = {
    'ing': 'action or process',
    'ed': 'past tense',
    'ly': 'in the manner of',
    'ness': 'state of being',
    'ment': 'result or act of',
    'tion': 'action or process',
    'sion': 'state or quality',
    'able': 'capable of',
    'ible': 'capable of'
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_word_file(path):
    words = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            word = parts[0]
            sentence = parts[1] if len(parts) > 1 and parts[1] else None
            pos = parts[2] if len(parts) > 2 and parts[2] else None
            definition = parts[3] if len(parts) > 3 and parts[3] else None
            words.append({'word': word, 'sentence': sentence, 'pos': pos, 'definition': definition})
    return words


def detect_affix(word):
    found = {'prefix': None, 'suffix': None, 'explanation': None}
    lw = word.lower()
    for p, meaning in COMMON_PREFIXES.items():
        if lw.startswith(p) and len(lw) > len(p) + 1:
            found['prefix'] = p
            found['explanation'] = meaning
            break
    for s, meaning in COMMON_SUFFIXES.items():
        if lw.endswith(s) and len(lw) > len(s) + 1:
            found['suffix'] = s
            found['explanation'] = meaning
            break
    return found


def create_definition_clue(word_data):
    """Create a sentence with the word replaced by a definition clue in italics"""
    if not word_data.get('sentence'):
        return f"Select the word that means: {word_data.get('definition', 'the correct word')}"
    
    sentence = word_data['sentence']
    word = word_data['word']
    
    # Replace the word with an italicized definition clue
    if word_data.get('definition'):
        clue = f"<i>{word_data['definition']}</i>"
    else:
        # If no definition provided, use a generic clue
        if word_data.get('pos'):
            clue = f"<i>a {word_data['pos']}</i>"
        else:
            clue = f"<i>the missing word</i>"
    
    # Simple replacement - replace the first occurrence of the word
    definition_sentence = sentence.replace(word, clue, 1)
    return definition_sentence


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'wordfile' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    file = request.files['wordfile']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        words = parse_word_file(path)
        for w in words:
            w.update(detect_affix(w['word']))
        session_file = filename + '.json'
        session_path = os.path.join(app.config['UPLOAD_FOLDER'], session_file)
        with open(session_path, 'w', encoding='utf-8') as sf:
            json.dump(words, sf, ensure_ascii=False)
        
        return redirect(url_for('select_test', session=session_file))
    else:
        flash('Invalid file type. Upload a .txt file.')
        return redirect(url_for('index'))


@app.route('/select_test')
def select_test():
    session = request.args.get('session')
    if not session:
        flash('No session')
        return redirect(url_for('index'))
    return render_template('select_test.html', session=session)


@app.route('/test')
def test():
    session = request.args.get('session')
    if not session:
        flash('No session')
        return redirect(url_for('index'))
    path = os.path.join(app.config['UPLOAD_FOLDER'], session)
    if not os.path.exists(path):
        flash('Session not found')
        return redirect(url_for('index'))
    with open(path, 'r', encoding='utf-8') as f:
        words = json.load(f)
    random.shuffle(words)
    return render_template('test.html', words=json.dumps(words))


@app.route('/definition_test')
def definition_test():
    session = request.args.get('session')
    if not session:
        flash('No session')
        return redirect(url_for('index'))
    path = os.path.join(app.config['UPLOAD_FOLDER'], session)
    if not os.path.exists(path):
        flash('Session not found')
        return redirect(url_for('index'))
    with open(path, 'r', encoding='utf-8') as f:
        words = json.load(f)
    
    # Create definition test questions
    questions = []
    for word_data in words:
        # Create the definition clue sentence
        definition_clue = create_definition_clue(word_data)
        
        # Select 3 random wrong answers + the correct one
        other_words = [w for w in words if w['word'] != word_data['word']]
        wrong_choices = random.sample(other_words, min(3, len(other_words)))
        
        choices = [{'word': word_data['word'], 'correct': True}] + \
                  [{'word': w['word'], 'correct': False} for w in wrong_choices]
        
        # Shuffle the choices
        random.shuffle(choices)
        
        questions.append({
            'definition': definition_clue,
            'correct_word': word_data['word'],
            'choices': choices
        })
    
    # Shuffle the questions
    random.shuffle(questions)
    
    return render_template('definition_test.html', questions=json.dumps(questions))


@app.route('/grade', methods=['POST'])
def grade():
    payload = request.get_json()
    responses = payload.get('responses', [])
    results = []
    correct_count = 0
    for r in responses:
        expected = r.get('word', '')
        student_sp = (r.get('spelling') or '').strip()
        spelled_ok = student_sp.lower() == expected.lower()
        pos_expected = r.get('pos_expected')
        pos_student = (r.get('pos') or '').strip()
        pos_ok = None
        if pos_expected:
            pos_ok = pos_student.lower() == pos_expected.lower()
        affix_ok = None
        if r.get('prefix') or r.get('suffix'):
            given = (r.get('affix_answer') or '').strip().lower()
            target = (r.get('prefix') or r.get('suffix')).lower()
            explanation = (r.get('explanation') or '').lower()
            affix_ok = False
            if given:
                # direct match of prefix/suffix
                if target in given:
                    affix_ok = True
                else:
                    # remove punctuation from explanation, split into keywords
                    import re
                    keywords = re.findall(r'\b\w+\b', explanation)
                    # give credit if any keyword appears in student's answer
                    if any(kw in given for kw in keywords):
                        affix_ok = True
        points = 0
        max_points = 1 + (1 if pos_expected else 0) + (1 if r.get('prefix') or r.get('suffix') else 0)
        if spelled_ok:
            points += 1
        if pos_expected and pos_ok:
            points += 1
        if (r.get('prefix') or r.get('suffix')) and affix_ok:
            points += 1
        if points == max_points:
            correct_count += 1
        results.append({
            'word': expected,
            'student_spelling': student_sp,
            'spelling_ok': spelled_ok,
            'correct_spelling': expected,
            'pos_student': pos_student,
            'pos_expected': pos_expected,
            'pos_ok': pos_ok,
            'affix_answer': r.get('affix_answer'),
            'affix_ok': affix_ok,
            'affix_explanation': r.get('explanation'),
            'points': points,
            'max_points': max_points,
            'sentence': r.get('sentence')
        })
    summary = {'total_items': len(results), 'fully_correct': correct_count}
    return {'results': results, 'summary': summary}


@app.route('/grade_definition_test', methods=['POST'])
def grade_definition_test():
    payload = request.get_json()
    responses = payload.get('responses', [])
    results = []
    correct_count = 0
    
    for r in responses:
        definition = r.get('definition', '')
        correct_word = r.get('correct_word', '')
        selected_word = r.get('selected_word', '')
        
        is_correct = selected_word.lower() == correct_word.lower()
        if is_correct:
            correct_count += 1
            
        results.append({
            'definition': definition,
            'correct_word': correct_word,
            'selected_word': selected_word,
            'correct': is_correct
        })
    
    summary = {'total_items': len(results), 'correct_count': correct_count}
    return {'results': results, 'summary': summary}


if __name__ == '__main__':
    app.run(debug=True)