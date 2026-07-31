#!/usr/bin/env python3
"""
Script de validación: Verifica que ui/main_ui.py no tenga errores de sintaxis
"""
import sys
import ast

def check_syntax(filepath):
    """Verifica sintaxis de un archivo Python"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        print(f"OK {filepath}: Sintaxis válida")
        return True
    except SyntaxError as e:
        print(f"ERROR {filepath}: Error de sintaxis en línea {e.lineno}")
        print(f"   {e.msg}")
        return False
    except Exception as e:
        print(f"ERROR {filepath}: Error - {e}")
        return False

if __name__ == "__main__":
    files = [
        "ui/main_ui.py",
        "core/scanner.py",
        "core/storage.py",
        "db_manager_app.py"
    ]
    
    all_valid = True
    for f in files:
        if not check_syntax(f):
            all_valid = False
    
    if all_valid:
        print("\nOK Todos los archivos tienen sintaxis válida")
        sys.exit(0)
    else:
        print("\nERROR Hay errores de sintaxis que corregir")
        sys.exit(1)
