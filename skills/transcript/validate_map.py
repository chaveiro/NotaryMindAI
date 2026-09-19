#!/usr/bin/env python3
"""
Validation of docs_logical_map.json — `map` quality check
Detects: multiple sellers, procuradores errados, papéis genealógicos inconsistentes
Uso: python3 validate_map.py [/path/to/project]

Ref: SKILL.md Modo C (Regras de Qualidade Aprimoradas)
Data: 2026-09-13
"""

import json
import re
import sys
import os
from pathlib import Path
from collections import defaultdict

# Auto-detect project path
if len(sys.argv) > 1:
    PROJECT_PATH = Path(sys.argv[1])
else:
    cwd = Path.cwd()
    PROJECT_PATH = None
    for attempt in [cwd, cwd.parent, cwd.parent.parent]:
        if (attempt / "docs_logical_map.json").exists():
            PROJECT_PATH = attempt
            break
    if not PROJECT_PATH:
        print("Usage: python3 validate_map.py [/path/to/project]", file=sys.stderr)
        print("Or run from within a project directory with docs_logical_map.json", file=sys.stderr)
        sys.exit(1)

IMG_DIR = PROJECT_PATH / "metadata"
MAP_PATH = PROJECT_PATH / "docs_logical_map.json"

def normalize_name(name):
    """Normalizes name for comparison"""
    if not name:
        return ""
    return name.lower().replace(" de ", "").replace(" e ", " ").split("(")[0].strip()

def load_data():
    """Loads map.json and image JSONs"""
    with open(MAP_PATH) as f:
        map_data = json.load(f)
    if not isinstance(map_data.get("logical_documents"), list):
        raise ValueError(
            f"{MAP_PATH} must contain a 'logical_documents' array "
            "(see skills/transcript/SCHEMA.md)"
        )
    
    images = {}
    for p in IMG_DIR.glob("*.json"):
        with open(p) as f:
            data = json.load(f)
            img_name = data.get("imagem", p.name.replace(".json", ".jpg"))
            images[img_name] = data
    
    return map_data, images

def check_transaction_relations(map_data, images):
    """Opção A: cada DL com transação deve ter relações sale/purchase/mortgage na
    genealogia (image JSONs), e cada extremo dessas relações deve existir como pessoa.
    This way the viewer can draw each seller/buyer as an individual node."""
    issues = []
    TX_RELS = {"vende a", "compra a", "hipoteca a favor de"}

    def norm(s):
        return " ".join((s or "").lower().split())

    for doc in map_data.get("logical_documents", []):
        doc_id = doc.get("id")
        tx = doc.get("transaction") or {}
        if not tx or not (tx.get("seller") or tx.get("buyer")):
            continue

        pessoas_nomes = set()
        rels_tx = []
        for img in doc.get("images", []):
            g = images.get(img, {}).get("genealogia", {})
            for p in g.get("pessoas", []):
                pessoas_nomes.add(norm(p.get("nome")))
                for v in p.get("variantes", []):
                    pessoas_nomes.add(norm(v))
            for r in g.get("relacoes", []):
                if r.get("relacao") in TX_RELS or r.get("categoria") in {"venda", "compra", "hipoteca"}:
                    rels_tx.append(r)

        # 1) Tem de existir pelo menos uma relação transacional na genealogia
        if not rels_tx:
            issues.append({
                "doc_id": doc_id,
                "tipo": "missing_tx_relations",
                "msg": ("transaction in map but NO relations sale/purchase/mortgage na "
                        "genealogy of image JSONs (missing extraction Option A)"),
            })
            continue

        # 2) Cada extremo das relações tem de existir como pessoa (senão nó invisível)
        for r in rels_tx:
            for lado in ("de", "para"):
                nome = norm(r.get(lado))
                if nome and nome not in pessoas_nomes:
                    issues.append({
                        "doc_id": doc_id,
                        "tipo": "tx_relation_orphan",
                        "msg": (f"relation '{r.get('de')} {r.get('relacao')} {r.get('para')}' "
                            f"has endpoint '{r.get(lado)}' missing from genealogy persons"),
                    })

    return issues

def check_procurators(map_data, images):
    """Verifica se procuradores batem entre map.json e OCR observações"""
    issues = []
    
    for doc in map_data.get("logical_documents", []):
        doc_id = doc.get("id")
        tx = doc.get("transaction") or {}
        
        vend = (tx.get("seller") or "").lower()
        comp = (tx.get("buyer") or "").lower()
        
        # Procurador em map?
        if "procurador" not in vend and "procurador" not in comp:
            continue
        
        for img in doc.get("images", []):
            if img not in images:
                continue
            
            obs = images[img].get("ocr_metadata", {}).get("observacoes", "").lower()
            
            if "procurador" not in obs:
                continue
            
            # Extrair nomes
            match_map = re.search(r"procurador\s+([a-záçã ]+?)[\.,\)]", vend + " " + comp)
            match_obs = re.search(r"procurador\s+([a-záçã ]+?)[\.,\)]", obs)
            
            if match_map and match_obs:
                proc_map = match_map.group(1).strip()
                proc_obs = match_obs.group(1).strip()
                
                # Comparar (primeiro 6 chars para tolerância)
                if normalize_name(proc_map)[:6] != normalize_name(proc_obs)[:6]:
                    issues.append({
                        "doc_id": doc_id,
                        "tipo": "procurator_mismatch",
                        "msg": f"Procurator mismatch: map='{proc_map}' vs OCR='{proc_obs}'",
                        "procurador_map": proc_map,
                        "procurador_obs": proc_obs
                    })
    
    return issues

def check_genealogy_roles(map_data, images):
    """Verifica se papéis genealógicos batem com transação"""
    issues = []
    
    for doc in map_data.get("logical_documents", []):
        doc_id = doc.get("id")
        tx = doc.get("transaction") or {}
        
        for img in doc.get("images", []):
            if img not in images:
                continue
            
            # Papéis na genealogia
            gen_pessoas = images[img].get("genealogia", {}).get("pessoas", [])
            
            for p in gen_pessoas:
                papel = (p.get("papel") or "").lower()
                nome = p.get("nome", "")
                
                # Se genealogia marca como "buyer" mas transcricao diz "seller"
                if "buyer" in papel and tx.get("seller") and nome in tx.get("seller", ""):
                    issues.append({
                        "doc_id": doc_id,
                        "tipo": "genealogy_role_mismatch",
                        "msg": f"'{nome}' is marked as buyer in genealogy but is a seller in the map",
                        "pessoa": nome,
                        "papel_gen": papel,
                        "localizacao": img
                    })
    
    return issues

def print_issues(all_issues):
    """Formata e imprime issues"""
    if not all_issues:
        print("\n✅ No transaction validation errors detected")
        return False
    
    print(f"\n❌ Found {len(all_issues)} error(s):\n")
    
    by_type = defaultdict(list)
    for issue in all_issues:
        by_type[issue.get("tipo")].append(issue)
    
    for tipo, issues in sorted(by_type.items()):
        print(f"\n📋 {tipo.upper()} ({len(issues)}):")
        for issue in issues:
            print(f"  • {issue['doc_id']}: {issue['msg']}")
    
    return True

def main():
    print("\n🔍 Validating docs_logical_map.json ...")
    print("=" * 70)
    
    try:
        map_data, images = load_data()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"❌ Error loading data: {e}")
        return 1
    
    # Executar verificações
    issues = [
        *check_transaction_relations(map_data, images),
        *check_procurators(map_data, images),
        *check_genealogy_roles(map_data, images)
    ]
    
    # Imprimir resultados
    has_errors = print_issues(issues)
    
    print(f"\n{'='*70}")
    
    # Resumo
    stats = {
        "missing_tx_relations": len([i for i in issues if i["tipo"] == "missing_tx_relations"]),
        "tx_relation_orphan": len([i for i in issues if i["tipo"] == "tx_relation_orphan"]),
        "procurator_mismatch": len([i for i in issues if i["tipo"] == "procurator_mismatch"]),
        "genealogy_role_mismatch": len([i for i in issues if i["tipo"] == "genealogy_role_mismatch"])
    }
    
    print(f"\n📊 Summary: {sum(stats.values())} problem(s)")
    for tipo, count in stats.items():
        if count > 0:
            print(f"   • {tipo}: {count}")
    
    return 1 if has_errors else 0

if __name__ == "__main__":
    sys.exit(main())
