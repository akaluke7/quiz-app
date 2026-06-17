import fitz
from pdf_parser import parse_pdf
with open('database-teoria.pdf', 'rb') as f:
    questions = parse_pdf(f.read(), use_db=False)

for i, q in enumerate(questions):
    if len(q['options']) > 5:
        print(f'--- Question index {i} has {len(q["options"])} options ---')
        print(q['question_text'].strip()[:100] + '...')
        for j, o in enumerate(q['options']):
            print(f'  Opt {j+1}: {o["text"].strip()[:50]}...')