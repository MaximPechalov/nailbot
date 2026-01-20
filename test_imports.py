import importlib

modules = [
    'telegram',
    'gspread',
    'google.auth',
    'dotenv'
]

for module in modules:
    try:
        importlib.import_module(module.split('.')[0])
        print(f"✅ {module} установлен")
    except ImportError as e:
        print(f"❌ {module} НЕ установлен: {e}")