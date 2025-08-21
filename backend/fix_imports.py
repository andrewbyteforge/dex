import re 
 
# Fix ai.py 
with open('app/api/ai.py', 'r') as f: 
    content = f.read() 
 
content = re.sub(r'from backend\.app\.ai\.', 'from ..ai.', content) 
 
with open('app/api/ai.py', 'w') as f: 
    f.write(content) 
 
print('Fixed ai.py imports') 
