# pyrefly: ignore [missing-import]
import streamlit as st
import random
import re
from pdf_parser import parse_pdf

st.set_page_config(page_title="PDF Quiz App", page_icon="🎓", layout="centered")

# Custom CSS for modern UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Allarga il contenitore principale di Streamlit per sfruttare meglio lo schermo */
    .block-container {
        max-width: 900px !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 18px !important;
    }

    .stButton>button {
        width: 100%;
        min-height: 60px !important;
        border-radius: 12px !important;
        padding: 18px 24px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Touch targets ampi per st.radio */
    .stRadio > div[role="radiogroup"] > label {
        background-color: var(--secondary-background-color) !important;
        border: 2px solid transparent !important;
        border-radius: 12px !important;
        padding: 18px 24px !important;
        min-height: 60px !important;
        margin-bottom: 12px !important;
        cursor: pointer !important;
        transition: all 0.2s ease-in-out !important;
        color: var(--text-color) !important;
        display: flex;
        align-items: center;
    }

    .stRadio > div[role="radiogroup"] > label p {
        font-size: 20px !important;
    }

    .stRadio > div[role="radiogroup"] > label:hover {
        border-color: var(--primary-color) !important;
    }

    .stRadio > div[role="radiogroup"] > label:focus-within {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25) !important;
    }

    .option-answered {
        width: 100%;
        border-radius: 12px;
        padding: 18px 24px;
        font-size: 20px;
        font-weight: 500;
        margin-bottom: 12px;
        border: 2px solid transparent;
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        min-height: 60px;
        display: flex;
        align-items: center;
    }

    .option-correct {
        background-color: rgba(34, 197, 94, 0.1) !important;
        border-color: #22c55e !important;
        border-width: 3px !important;
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    .option-incorrect {
        background-color: rgba(239, 68, 68, 0.1) !important;
        border-color: #ef4444 !important;
        border-width: 3px !important;
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    .option-neutral {
        background-color: var(--secondary-background-color) !important;
        border-color: gray !important;
        border-width: 3px !important;
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    .question-text {
        font-size: 28px;
        font-weight: 600;
        color: var(--text-color);
        margin-bottom: 24px;
        line-height: 1.6;
    }

    .question-divider {
        margin-top: 24px;
        margin-bottom: 24px;
        border-bottom: 1px solid var(--text-color);
        opacity: 0.2;
    }

    .correct-feedback {
        color: var(--text-color);
        background-color: rgba(34, 197, 94, 0.1);
        padding: 16px;
        border-radius: 8px;
        border-left: 5px solid #22c55e;
        margin-top: 20px;
        font-weight: 500;
        font-size: 20px;
    }
    
    .incorrect-feedback {
        color: var(--text-color);
        background-color: rgba(239, 68, 68, 0.1);
        padding: 16px;
        border-radius: 8px;
        border-left: 5px solid #ef4444;
        margin-top: 20px;
        font-weight: 500;
        font-size: 20px;
    }
</style>
""", unsafe_allow_html=True)

def chunk_question_text(text):
    keywords = r'\b(Quale|Quali|Cosa|Chi|Come|Perché|Trovare|Calcolare|Determinare|Indicare|Selezionare|In che modo|Non è|È falso|È vero)\b'
    return re.sub(keywords, r'**\1**', text, flags=re.IGNORECASE)

# Initialize Session State
if 'app_state' not in st.session_state:
    st.session_state.app_state = 'upload' # states: upload, config, quiz, result
if 'all_questions' not in st.session_state:
    st.session_state.all_questions = []
if 'quiz_questions' not in st.session_state:
    st.session_state.quiz_questions = []
if 'current_q_idx' not in st.session_state:
    st.session_state.current_q_idx = 0
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

def reset_state():
    st.session_state.app_state = 'upload'
    st.session_state.all_questions = []
    st.session_state.quiz_questions = []
    st.session_state.current_q_idx = 0
    st.session_state.score = 0
    st.session_state.user_answers = {}

def calculate_similarity(text1, text2):
    """Calcola la similarità basata sulle parole chiave per evitare domande molto simili."""
    # Estrae le parole lunghe almeno 4 caratteri per ignorare articoli/preposizioni
    words1 = set(re.findall(r'\b\w{4,}\b', text1.lower()))
    words2 = set(re.findall(r'\b\w{4,}\b', text2.lower()))
    if not words1 or not words2:
        return 0.0
    # Misura l'intersezione (Overalp coefficient)
    intersection = words1.intersection(words2)
    return len(intersection) / min(len(words1), len(words2))

def start_quiz(num_questions):
    all_q = st.session_state.all_questions
    
    if num_questions >= len(all_q):
        selected = list(all_q)
        random.shuffle(selected)
    else:
        selected = []
        pool = list(all_q)
        random.shuffle(pool)
        
        for q in pool:
            if len(selected) == num_questions:
                break
                
            # Verifica che la domanda non sia troppo simile (es. > 50% parole in comune) a quelle già scelte
            too_similar = False
            for sq in selected:
                if calculate_similarity(q['question_text'], sq['question_text']) > 0.5:
                    too_similar = True
                    break
                    
            if not too_similar:
                selected.append(q)
                
        # Se non si trovano abbastanza domande diverse, riempi con le rimanenti
        if len(selected) < num_questions:
            remaining = [q for q in pool if q not in selected]
            selected.extend(remaining[:num_questions - len(selected)])
            
    st.session_state.quiz_questions = selected
    st.session_state.app_state = 'quiz'
    st.session_state.current_q_idx = 0
    st.session_state.score = 0
    st.session_state.user_answers = {}

# --- VIEW: UPLOAD ---
if st.session_state.app_state == 'upload':
    st.title("🎓 PDF to Quiz Converter")
    st.write("Carica un file PDF contenente domande a risposta multipla. Il sistema estrapolerà le domande e creerà un quiz interattivo.")
    
    uploaded_file = st.file_uploader("Trascina qui o seleziona un file PDF", type=["pdf"])
    
    if uploaded_file is not None:
        with st.spinner("Analisi del PDF in corso..."):
            try:
                questions = parse_pdf(uploaded_file.read())
                if len(questions) > 0:
                    st.session_state.all_questions = questions
                    st.session_state.app_state = 'config'
                    st.rerun()
                else:
                    st.error("Impossibile trovare domande valide nel PDF. Assicurati che il formato sia corretto (es. '1. Domanda', 'a) Opzione').")
            except Exception as e:
                st.error(f"Errore durante l'elaborazione del file: {e}")

# --- VIEW: CONFIGURATION ---
elif st.session_state.app_state == 'config':
    st.title("⚙️ Configurazione Quiz")
    st.success(f"PDF analizzato con successo! Trovate {len(st.session_state.all_questions)} domande valide.")
    
    num_q = st.slider("Quante domande vuoi affrontare in questa sessione?", 
                      min_value=1, 
                      max_value=len(st.session_state.all_questions), 
                      value=min(10, len(st.session_state.all_questions)))
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Avvia Quiz", type="primary"):
            start_quiz(num_q)
            st.rerun()
    with col2:
        if st.button("Carica un altro PDF"):
            reset_state()
            st.rerun()

# --- VIEW: QUIZ INTERACTIVE ---
elif st.session_state.app_state == 'quiz':
    total_q = len(st.session_state.quiz_questions)
    curr_idx = st.session_state.current_q_idx
    q = st.session_state.quiz_questions[curr_idx]
    
    st.progress((curr_idx) / total_q)
    st.write(f"**Domanda {curr_idx + 1} di {total_q}**")
    
    formatted_q = chunk_question_text(q["question_text"])
    st.markdown(f'<div class="question-text">{formatted_q}</div>', unsafe_allow_html=True)
    st.markdown('<div class="question-divider"></div>', unsafe_allow_html=True)
    
    # Check if this question was already answered
    is_answered = curr_idx in st.session_state.user_answers
    
    has_correct_opt = any(opt['is_correct'] for opt in q['options'])
    if not has_correct_opt:
        st.warning("⚠️ Nota: la risposta corretta per questa domanda non è indicata nel database o nel PDF originale.")
    
    if is_answered:
        user_opt_idx = st.session_state.user_answers[curr_idx]
        for i, opt in enumerate(q['options']):
            if not has_correct_opt:
                if i == user_opt_idx:
                    st.markdown(f'<div class="option-answered option-neutral" tabindex="0">✔️ <b>{opt["text"]}</b> (Scelta registrata)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="option-answered" tabindex="0">⚪ {opt["text"]}</div>', unsafe_allow_html=True)
            else:
                if i == user_opt_idx:
                    if opt['is_correct']:
                        st.markdown(f'<div class="option-answered option-correct" tabindex="0">✔️ <b>{opt["text"]}</b></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="option-answered option-incorrect" tabindex="0">❌ <del>{opt["text"]}</del></div>', unsafe_allow_html=True)
                else:
                    if opt['is_correct']:
                        st.markdown(f'<div class="option-answered option-correct" tabindex="0">✔️ <b>{opt["text"]}</b> (Risposta Corretta)</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="option-answered" tabindex="0">⚪ {opt["text"]}</div>', unsafe_allow_html=True)
    else:
        with st.form(key=f"form_{curr_idx}"):
            user_choice = st.radio(
                "Seleziona un'opzione:",
                options=range(len(q['options'])),
                format_func=lambda i: q['options'][i]['text'],
                label_visibility="collapsed"
            )
            submit_btn = st.form_submit_button("Conferma Risposta", type="primary", use_container_width=True)
            if submit_btn:
                st.session_state.user_answers[curr_idx] = user_choice
                if q['options'][user_choice]['is_correct'] or not has_correct_opt:
                    st.session_state.score += 1
                st.rerun()
                
    if is_answered:
        user_opt_idx = st.session_state.user_answers[curr_idx]
        if not has_correct_opt:
            st.markdown('<div class="correct-feedback" style="background-color: var(--secondary-background-color); border-color: gray; color: var(--text-color);">Risposta salvata. (Nessuna risposta corretta definita nel PDF)</div>', unsafe_allow_html=True)
        else:
            is_correct = q['options'][user_opt_idx]['is_correct']
            if is_correct:
                st.markdown('<div class="correct-feedback">Hai risposto correttamente! 🎉</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="incorrect-feedback">Risposta errata. Rivedi l\'opzione corretta sopra.</div>', unsafe_allow_html=True)
            
        st.write("---")
        if curr_idx < total_q - 1:
            if st.button("Prossima Domanda ➡️", type="primary"):
                st.session_state.current_q_idx += 1
                st.rerun()
        else:
            if st.button("Vedi Risultati 🏆", type="primary"):
                st.session_state.app_state = 'result'
                st.rerun()

# --- VIEW: RESULTS ---
elif st.session_state.app_state == 'result':
    st.title("🏆 Risultati Finali")
    total_q = len(st.session_state.quiz_questions)
    score = st.session_state.score
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem; background-color: var(--secondary-background-color); border-radius: 10px; margin-bottom: 2rem;'>
        <h2 style='color: var(--text-color);'>Hai risposto correttamente a</h2>
        <h1 style='color: var(--primary-color); font-size: 3rem;'>{score} <span style='font-size: 2rem; color: var(--text-color); opacity: 0.7;'>su {total_q}</span></h1>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Riavvia con nuove domande", type="primary"):
            st.session_state.app_state = 'config'
            st.rerun()
    with col2:
        if st.button("Carica un nuovo PDF"):
            reset_state()
            st.rerun()
