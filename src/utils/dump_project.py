import os
from datetime import datetime
from pathlib import Path

# --- CONFIGURAÇÕES ---
# Extensões de arquivos que você deseja ler
EXTENSOES_PERMITIDAS = {".py", ".js", ".html", ".css", ".md", ".txt", ".json", ".abap"}

# Pastas ou padrões que devem ser ignorados
PADROES_IGNORAR = {
    "__pycache__",
    ".git",
    ".venv",
    ".zip",
    ".lua",
    "node_modules",
    "static",
    ".vscode",
    "venv",
    "dist",
    "dump",
}  # , 'build', 'target', 'out', 'bin', 'obj'}

# Mapeia a pasta 'src' (voltando 2 níveis a partir de src/utils/script.py)
DIRETORIO_SRC = Path(__file__).resolve().parent.parent
DIRETORIO_DUMP = DIRETORIO_SRC / "dump"

# Cria a pasta dump automaticamente caso não exista
DIRETORIO_DUMP.mkdir(parents=True, exist_ok=True)


def obter_nome_arquivo_saida():

    return DIRETORIO_DUMP / f"dump-{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"


def deve_ignorar(caminho):
    """Verifica se o caminho contém algum dos padrões de exclusão."""
    for padrao in PADROES_IGNORAR:
        if padrao in caminho.parts or any(padrao in part for part in caminho.parts):
            return True
    return False


def gerar_dump():
    diretorio_atual = DIRETORIO_SRC
    arquivo_saida = obter_nome_arquivo_saida()
    conteudo_final = []
    estrutura_pastas = []

    # 1. Mapeando a estrutura de pastas
    estrutura_pastas.append(f"=== ESTRUTURA DO PROJETO: {diretorio_atual.name} ===\n")

    for root, dirs, files in os.walk(diretorio_atual):
        path_root = Path(root)
        if deve_ignorar(path_root):
            continue

        nivel = len(path_root.relative_to(diretorio_atual).parts)
        indentacao = "  " * nivel
        estrutura_pastas.append(f"{indentacao}📂 {path_root.name}/")

        sub_indentacao = "  " * (nivel + 1)
        for f in files:
            # Ignora o arquivo de saída caso ele já tenha sido criado em uma execução anterior
            if f.startswith("dump_") and f.endswith(".txt"):
                continue
            if Path(f).suffix in EXTENSOES_PERMITIDAS:
                estrutura_pastas.append(f"{sub_indentacao}📄 {f}")

    conteudo_final.append("\n".join(estrutura_pastas))
    conteudo_final.append("\n\n" + "=" * 50 + "\n")
    conteudo_final.append("=== CONTEÚDO DOS ARQUIVOS ===\n")

    # 2. Lendo o conteúdo dos arquivos
    for arquivo in diretorio_atual.rglob("*"):
        if (
            arquivo.is_file()
            and not deve_ignorar(arquivo)
            and arquivo.suffix in EXTENSOES_PERMITIDAS
        ):
            # Não inclui o próprio script nem arquivos de dump anteriores no conteúdo
            if arquivo.name == "projeto_para_ia.py" or (
                arquivo.name.startswith("dump_") and arquivo.suffix == ".txt"
            ):
                continue

            try:
                rel_path = arquivo.relative_to(diretorio_atual)
                conteudo_final.append(f"\n--- ARQUIVO: {rel_path} ---")

                with open(arquivo, "r", encoding="utf-8", errors="ignore") as f:
                    conteudo_final.append(f.read())

                conteudo_final.append("\n--- FIM DO ARQUIVO ---\n")
            except Exception as e:
                conteudo_final.append(f"\n[ERRO AO LER {arquivo.name}: {e}]\n")

    # 3. Salvando no arquivo com o nome dinâmico
    with open(arquivo_saida, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(conteudo_final))

    print(f"✅ Dump concluído com sucesso!")
    print(f"📄 Arquivo gerado: {arquivo_saida}")


if __name__ == "__main__":
    gerar_dump()
