import os
import re

files_to_process = [
    'CONTRIBUTING.md',
    'MAC版本智能体部署方法.txt',
    'PA_Agent使用文档.md',
    'CandleCast使用文档.md', # in case it was already renamed
    'README.md',
    'SECURITY.md',
    '把这个扔给龙虾-智能体部署方法.txt',
    '运行智能体.bat'
]

replacements = [
    (r'\bPA Agent\b', 'CandleCast'),
    (r'\bPA_Agent\b', 'CandleCast'),
    (r'\bPA-Agent\b', 'CandleCast'),
    (r'\bPA 智能体\b', 'CandleCast 智能体'),
    (r'\bPA智能体\b', 'CandleCast智能体'),
    (r'\bpa_agent\b', 'candle_cast'),
    (r'\bpa-agent\b', 'candle-cast'),
    (r'\bPA\b', 'CandleCast')
]

for filename in files_to_process:
    filepath = os.path.join(r'S:\PA_Agent', filename)
    if not os.path.exists(filepath):
        continue
    
    content = None
    encodings = ['utf-8', 'gbk', 'utf-16']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            # If successful, we remember the encoding
            used_enc = enc
            break
        except UnicodeDecodeError:
            pass
            
    if content is None:
        print(f"Could not read {filename}")
        continue
        
    original_content = content
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
        
    if content != original_content:
        with open(filepath, 'w', encoding=used_enc) as f:
            f.write(content)
        print(f"Updated {filename}")

# Rename the file if needed
old_doc_name = os.path.join(r'S:\PA_Agent', 'PA_Agent使用文档.md')
new_doc_name = os.path.join(r'S:\PA_Agent', 'CandleCast使用文档.md')
if os.path.exists(old_doc_name):
    os.rename(old_doc_name, new_doc_name)
    print(f"Renamed {old_doc_name} to {new_doc_name}")
