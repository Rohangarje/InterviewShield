import ast
import os

files_to_check = [
    r'd:\Projects\InterviewShield\backend\detector\views.py',
    r'd:\Projects\InterviewShield\backend\detector\urls.py',
    r'd:\Projects\InterviewShield\backend\detector\models.py',
    r'd:\Projects\InterviewShield\backend\detector\utils\auth.py',
    r'd:\Projects\InterviewShield\backend\detector\utils\mongo_client.py',
]

for filepath in files_to_check:
    print(f"\n{'='*60}")
    print(f"Checking: {filepath}")
    print('='*60)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        print("✅ No syntax errors")
    except SyntaxError as e:
        print(f"❌ SYNTAX ERROR at line {e.lineno}: {e.msg}")
        print(f"   {e.text}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
