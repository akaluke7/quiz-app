# pyrefly: ignore [missing-import]
import fitz
import re
import os

_db_questions = None  # Cached database-teoria questions

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'^\s*\d+[\.\)]\s*', '', text) # remove leading question number
    text = re.sub(r'^\s*\(?[a-fA-F]\)?[\.\)]?\s*', '', text) # remove leading option letter
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def option_similarity(opt1, opt2):
    opt1_clean = re.sub(r'^\s*\(?[a-fA-F]\)?[\.\)]?\s*', '', opt1.lower())
    opt2_clean = re.sub(r'^\s*\(?[a-fA-F]\)?[\.\)]?\s*', '', opt2.lower())
    
    words1 = set(re.findall(r'\w+', opt1_clean))
    words2 = set(re.findall(r'\w+', opt2_clean))
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    return len(intersection) / min(len(words1), len(words2))

def load_database_teoria():
    global _db_questions
    if _db_questions is not None:
        return _db_questions
    
    db_filename = "database-teoria.pdf"
    possible_paths = [
        db_filename,
        os.path.join(os.path.dirname(__file__), db_filename),
        os.path.join(os.getcwd(), db_filename)
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    _db_questions = parse_pdf(f.read(), use_db=False)
                    return _db_questions
            except Exception as e:
                print(f"Error loading database-teoria.pdf: {e}")
                
    _db_questions = []
    return _db_questions

def parse_pdf(file_bytes, use_db=True):
    """
    Parses a PDF file and returns a list of dictionaries containing questions and options.
    It looks for questions formatted as "1. ", "10) " and options as "a) ", "(A) ".
    Correct answers are identified if the text is bold or contains "(Nota:".
    If use_db is True, it will attempt to match questions against database-teoria.pdf
    to resolve correct answers.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    questions = []
    current_question = None
    current_option = None
    
    # Regex per riconoscere domande: es. "1.", "10.", "1)", "10)"
    re_question = re.compile(r"^\s*\d+[\.\)]\s*(.*)")
    # Regex per riconoscere opzioni: es. "(a)", "a)", "A.", supporta fino a f
    re_option = re.compile(r"^\s*(?:\(([a-fA-F])\)|([a-fA-F])[\.\)])\s+(.*)")
    
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:  # text block
                for l in b["lines"]:
                    # Join text spans for regex matching
                    line_text = "".join([s["text"] for s in l["spans"]]).strip()
                    if not line_text:
                        continue
                    
                    # Ignore watermarks
                    if "scaricato da" in line_text.lower() or "lomoarcpsd" in line_text.lower():
                        continue
                        
                    cleaned_line = re.sub(r'^[●\-*•\u200b\s]+', '', line_text)
                    if not cleaned_line:
                        continue
                        
                    q_match = re_question.match(cleaned_line)
                    o_match = re_option.match(cleaned_line)
                    
                    if q_match:
                        if current_question:
                            if current_question["options"]: # ensure it has options
                                questions.append(current_question)
                        current_question = {
                            "question_text": cleaned_line + "\n",
                            "options": []
                        }
                        current_option = None
                        
                    elif o_match and current_question:
                        opt_letter = (o_match.group(1) or o_match.group(2)).lower()
                        # Se troviamo un'opzione 'a' ma la domanda attuale ha già opzioni,
                        # vuol dire che è iniziata una nuova domanda il cui testo mancava nel PDF.
                        if opt_letter == 'a' and len(current_question["options"]) > 0:
                            questions.append(current_question)
                            current_question = {
                                "question_text": "[Testo della domanda mancante nel PDF originale]\n",
                                "options": []
                            }

                        # Check if any span in this line is bold (flags & 16 is bold in fitz)
                        is_bold = any((s["flags"] & 16 != 0) or ("bold" in s["font"].lower()) for s in l["spans"])
                        is_correct = is_bold or ("(Nota:" in cleaned_line) or ("(nota:" in cleaned_line.lower())
                        
                        current_option = {
                            "text": cleaned_line + "\n",
                            "is_correct": is_correct
                        }
                        current_question["options"].append(current_option)
                        
                    else:
                        # Continuation of current option or question
                        if current_option:
                            current_option["text"] += cleaned_line + "\n"
                            if any((s["flags"] & 16 != 0) or ("bold" in s["font"].lower()) for s in l["spans"]) or ("(Nota:" in cleaned_line) or ("(nota:" in cleaned_line.lower()):
                                current_option["is_correct"] = True
                        elif current_question:
                            current_question["question_text"] += cleaned_line + "\n"
                            
    if current_question and current_question["options"]:
        questions.append(current_question)
        
    # Enrich from database-teoria.pdf if requested and there are questions without correct answers
    if use_db:
        db_qs = load_database_teoria()
        if db_qs:
            # Index DB by normalized question text
            db_map = {}
            for db_q in db_qs:
                norm = normalize_text(db_q["question_text"])
                if norm not in db_map:
                    db_map[norm] = []
                db_map[norm].append(db_q)
                
            for q in questions:
                # Only try lookup if this question doesn't already have a correct option marked
                if not any(opt["is_correct"] for opt in q["options"]):
                    norm_q = normalize_text(q["question_text"])
                    if norm_q in db_map:
                        candidates = db_map[norm_q]
                        
                        # Find candidate with highest option overlap similarity
                        best_candidate = None
                        best_score = -1
                        
                        for cand in candidates:
                            score = 0
                            for opt in q["options"]:
                                for cand_opt in cand["options"]:
                                    if option_similarity(opt["text"], cand_opt["text"]) >= 0.7:
                                        score += 1
                                        break
                            if score > best_score:
                                best_score = score
                                best_candidate = cand
                                
                        # Map correct answer from best_candidate to q
                        if best_candidate:
                            for opt in q["options"]:
                                for cand_opt in best_candidate["options"]:
                                    if cand_opt["is_correct"] and option_similarity(opt["text"], cand_opt["text"]) >= 0.7:
                                        opt["is_correct"] = True
                                        
    # --- CORREZIONE MANUALE ERRORI NEL PDF ---
    MANUAL_OVERRIDES = {
        # Frammento domanda (normalizzata) -> Frammento opzione corretta (normalizzata)
        "decisione di implementare la produzione di un dato bene in una determinata": "pull"
    }
    
    for q in questions:
        norm_q = normalize_text(q["question_text"])
        for q_snippet, correct_opt_snippet in MANUAL_OVERRIDES.items():
            if normalize_text(q_snippet) in norm_q:
                for opt in q["options"]:
                    if normalize_text(correct_opt_snippet) in normalize_text(opt["text"]):
                        opt["is_correct"] = True
                    else:
                        opt["is_correct"] = False

    return questions
