"""
Fix corrupted Jinja2 syntax in templates where delimiters are split across lines
"""
import re

def fix_template(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix {% ... %} patterns split across lines
    # Pattern: {\n            % ... %\n        }
    content = re.sub(r'\{\s*\n\s*%\s*([^%]+?)\s*%\s*\n\s*\}', r'{% \1 %}', content)
    
    # Fix {{ ... }} patterns split across lines  
    # Pattern: {\n                {\n                variable\n            }\n        }
    content = re.sub(r'\{\s*\n\s*\{\s*\n\s*([^\}]+?)\s*\n\s*\}\s*\n\s*\}', r'{{ \1 }}', content)
    
    # Also fix simpler {{ }} patterns
    # Pattern: {{ \n variable \n }}
    content = re.sub(r'\{\{\s*\n\s*([^\}]+?)\s*\n\s*\}\}', r'{{ \1 }}', content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Fixed {filepath}")
        return True
    else:
        print(f"ℹ️  No changes needed for {filepath}")
        return False

# Fix both templates
strategy_path = "api/templates/strategy.html"
multibets_path = "api/templates/multibets.html"

print("Fixing template syntax...")
fixed_strategy = fix_template(strategy_path)
fixed_multibets = fix_template(multibets_path)

if fixed_strategy or fixed_multibets:
    print("\n✅ Templates fixed! Server should auto-reload.")
else:
    print("\n⚠️  No fixes applied - templates may have different corruption pattern")
