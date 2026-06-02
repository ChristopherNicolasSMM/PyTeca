#!/usr/bin/env python3
# Script para corrigir automaticamente problemas de estilo em projetos Python.
# Cria backup antes de fazer qualquer alteração.
#
# Autor: Christopher N. S. M. Mauricio
# Uso: python corrigir_estilo_projeto.py
#
#
# Modo de uso:
#
## Modo interativo (pergunta a pasta)
# python corrigir_estilo_projeto.py
#
## Ou passe a pasta como argumento
# python corrigir_estilo_projeto.py "C:\Users\...\DEVStationFlask"
#
## Caminho relativo também funciona
# python corrigir_estilo_projeto.py ./DEVStationFlask

import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path


# ============================================================
# CORES PARA TERMINAL (Windows/Linux/Mac)
# ============================================================
class Cores:
    VERDE = "\033[92m"
    AMARELO = "\033[93m"
    VERMELHO = "\033[91m"
    AZUL = "\033[94m"
    RESET = "\033[0m"


def print_color(texto, cor=Cores.AZUL):
    print(f"{cor}{texto}{Cores.RESET}")


def run_command(cmd, description, cwd=None):
    """Executa um comando no shell e mostra o resultado"""
    print_color(f"\n📦 {description}...", Cores.AZUL)
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, text=True, capture_output=True
        )
        if result.returncode == 0:
            print_color(f"   ✅ {description} concluído!", Cores.VERDE)
            if result.stdout:
                print(f"   {result.stdout.strip()}")
            return True
        else:
            print_color(f"   ⚠️ Problema em: {description}", Cores.AMARELO)
            if result.stderr:
                print(f"   Erro: {result.stderr.strip()[:200]}")
            return False
    except Exception as e:
        print_color(f"   ❌ Erro ao executar: {e}", Cores.VERMELHO)
        return False


def criar_backup(pasta_origem):
    """Cria um arquivo ZIP de backup da pasta"""
    print_color("\n📦 Criando backup...", Cores.AZUL)

    # Nome do backup com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_backup = f"backup_{Path(pasta_origem).name}_{timestamp}.zip"

    # Local do backup (mesmo diretório da pasta original)
    caminho_backup = Path(pasta_origem).parent / nome_backup

    try:
        with zipfile.ZipFile(caminho_backup, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(pasta_origem):
                # Ignorar pastas virtuais e cache
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in [
                        "venv",
                        ".venv",
                        "env",
                        "__pycache__",
                        ".git",
                        ".pytest_cache",
                    ]
                ]

                for file in files:
                    if file.endswith((".pyc", ".pyo")):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(
                        file_path, start=Path(pasta_origem).parent
                    )
                    zipf.write(file_path, arcname)

        print_color(f"   ✅ Backup criado: {caminho_backup}", Cores.VERDE)
        return caminho_backup
    except Exception as e:
        print_color(f"   ❌ Erro ao criar backup: {e}", Cores.VERMELHO)
        return None


def verificar_dependencias():
    """Verifica e instala dependências necessárias"""
    print_color("\n🔧 Verificando dependências...", Cores.AZUL)

    dependencias = ["black", "autoflake", "isort", "flake8"]
    for dep in dependencias:
        result = subprocess.run(f"pip show {dep}", shell=True, capture_output=True)
        if result.returncode != 0:
            print_color(f"   ⚠️ {dep} não instalado. Instalando...", Cores.AMARELO)
            subprocess.run(f"pip install {dep}", shell=True)
        else:
            print_color(f"   ✅ {dep} já instalado", Cores.VERDE)

    print_color("   ✅ Todas as dependências verificadas!", Cores.VERDE)


def main():
    print_color("\n" + "=" * 70, Cores.AZUL)
    print_color("🔧 CORRETOR AUTOMÁTICO DE ESTILO PYTHON".center(70), Cores.AZUL)
    print_color("=" * 70, Cores.AZUL)
    print_color(f"\n👤 Autor: Christopher N. S. M. Mauricio", Cores.AMARELO)

    # ============================================================
    # 1. OBTER O CAMINHO DA PASTA
    # ============================================================
    print_color("\n📁 [1/6] Localizando o projeto...", Cores.AZUL)

    # Opção 1: passar como argumento
    if len(sys.argv) > 1:
        caminho_pasta = sys.argv[1]
    else:
        # Opção 2: perguntar ao usuário
        print_color("\n   Deseja utilizar o diretório SRC* ? Yes | No", Cores.AMARELO)
        usar_diretorio_src = input(f"\n  👉 Deseja continuar? (s/N): ").lower()
        if usar_diretorio_src.lower() in ["s", "sim", "y", "yes"]:
            caminho_pasta = Path(__file__).parent.parent.resolve()
        else:
            print_color(
                "\n   Digite o caminho da pasta do projeto Python:", Cores.AMARELO
            )
            print_color(
                "   (ex: C:\\Users\\...\\MeuProjeto ou ./MeuProjeto)", Cores.AMARELO
            )
            caminho_pasta = input("\n   👉 ").strip()

    # Validar caminho
    pasta = Path(caminho_pasta).resolve()
    if not pasta.exists():
        print_color(f"\n   ❌ Pasta não encontrada: {pasta}", Cores.VERMELHO)
        print_color("   Verifique o caminho e tente novamente.", Cores.AMARELO)
        sys.exit(1)

    if not pasta.is_dir():
        print_color(f"\n   ❌ O caminho não é uma pasta: {pasta}", Cores.VERMELHO)
        sys.exit(1)

    print_color(f"\n   ✅ Projeto encontrado: {pasta}", Cores.VERDE)

    # Confirmar com o usuário
    print_color(
        f"\n   ⚠️  ATENÇÃO: Este script irá MODIFICAR os arquivos da pasta:",
        Cores.AMARELO,
    )
    print_color(f"      {pasta}", Cores.AMARELO)
    resposta = input(f"\n   Deseja continuar? (s/N): ").lower()

    if resposta not in ["s", "sim", "y", "yes"]:
        print_color("\n   ❌ Operação cancelada pelo usuário.", Cores.VERMELHO)
        sys.exit(0)

    # ============================================================
    # 2. CRIAR BACKUP
    # ============================================================
    print_color("\n📦 [2/6] Criando backup da pasta...", Cores.AZUL)
    caminho_backup = criar_backup(pasta)

    if not caminho_backup:
        resposta = input("\n   Backup falhou. Continuar mesmo assim? (s/N): ").lower()
        if resposta not in ["s", "sim", "y", "yes"]:
            print_color("\n   ❌ Operação cancelada.", Cores.VERMELHO)
            sys.exit(1)

    # ============================================================
    # 3. INSTALAR DEPENDÊNCIAS
    # ============================================================
    print_color("\n📦 [3/6] Instalando/verificando dependências...", Cores.AZUL)
    verificar_dependencias()

    # ============================================================
    # 4. REMOVER IMPORTS NÃO UTILIZADOS
    # ============================================================
    print_color("\n🗑️  [4/6] Removendo imports não utilizados...", Cores.AZUL)
    run_command(
        "autoflake --in-place --remove-unused-variables --remove-all-unused-imports -r .",
        "Removendo imports não utilizados",
        cwd=str(pasta),
    )

    # ============================================================
    # 5. ORDENAR IMPORTS COM ISORT
    # ============================================================
    print_color("\n📋 [5/6] Ordenando imports...", Cores.AZUL)
    run_command("isort .", "Ordenando imports", cwd=str(pasta))

    # ============================================================
    # 6. FORMATAR COM BLACK
    # ============================================================
    print_color("\n🎨 [6/6] Formatando código com Black...", Cores.AZUL)
    run_command("black .", "Formatando código com Black", cwd=str(pasta))

    # ============================================================
    # 7. VERIFICAR RESULTADO FINAL
    # ============================================================
    print_color("\n🔍 [7/7] Verificando resultado final...", Cores.AZUL)
    print_color("\n" + "=" * 70, Cores.AZUL)

    run_command(
        "flake8 --exclude=venv,.venv,env,.env,__pycache__,build,dist --max-line-length=88 --statistics",
        "Verificando estilo final",
        cwd=str(pasta),
    )

    # ============================================================
    # 8. RESUMO FINAL
    # ============================================================
    print_color("\n" + "=" * 70, Cores.VERDE)
    print_color("✅ CORREÇÃO CONCLUÍDA!".center(70), Cores.VERDE)
    print_color("=" * 70, Cores.VERDE)

    print_color(f"\n📁 Pasta processada: {pasta}", Cores.AMARELO)
    if caminho_backup:
        print_color(f"💾 Backup salvo em: {caminho_backup}", Cores.AMARELO)

    print_color(
        f"\n⚠️  AINDA PODE HAVER ERROS QUE PRECISAM DE CORREÇÃO MANUAL:", Cores.AMARELO
    )
    print_color(
        "   - F821 (nome indefinido): adicionar imports faltantes", Cores.AMARELO
    )
    print_color(
        "   - F841 (variável não usada): verificar lógica (ou remover)", Cores.AMARELO
    )
    print_color(
        "   - E741 (variável 'l'): renomear para nome descritivo", Cores.AMARELO
    )
    print_color("   - E402 (import não no topo): mover imports", Cores.AMARELO)

    print_color(f"\n💡 Para verificar novamente:", Cores.AZUL)
    print_color(f"   cd {pasta}", Cores.VERDE)
    print_color(
        f"   flake8 --exclude=venv,.venv,env,.env,__pycache__,build,dist --max-line-length=88",
        Cores.VERDE,
    )

    print_color("\n" + "=" * 70, Cores.VERDE)
    print_color("🎉 FIM DO PROCESSO".center(70), Cores.VERDE)
    print_color("=" * 70, Cores.VERDE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_color("\n\n⚠️  Processo interrompido pelo usuário.", Cores.AMARELO)
        sys.exit(0)
    except Exception as e:
        print_color(f"\n❌ Erro inesperado: {e}", Cores.VERMELHO)
        sys.exit(1)
