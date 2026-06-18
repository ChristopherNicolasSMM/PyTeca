"""
utils/hooks_scaffold.py — Criação (única, não-destrutiva) dos arquivos
de hooks pré/pós por model.

Princípio central: regeneração e customização NUNCA compartilham o mesmo
arquivo. O gerador escreve livremente em book.py (controller), em
book_service.py (service) e em book_routes.py (routes) a cada --overwrite.
Os arquivos *_hooks.py ao lado de cada um são escritos UMA VEZ — se já
existirem, o gerador nunca toca neles novamente, independente de
--overwrite.

Isso elimina por construção o risco que motivou esta funcionalidade:
"eu edito o controller gerado e perco a edição ao regenerar". Com hooks,
você nunca edita o gerado — edita o _hooks.py ao lado, que é seu para
sempre.

Ver: docs/manual/07-customizacao-hooks.md
"""
from __future__ import annotations

from pathlib import Path

# Pontos de hook disponíveis por camada — mantidos em um único lugar para
# que o scaffold (texto do stub) e o ponto de chamada real no .j2 nunca
# fiquem dessincronizados quanto a quais nomes de função existem.
CONTROLLER_HOOKS = [
    ("pbo_list", "Antes de montar a query de listagem. Retorne uma Response para interceptar totalmente (ex: redirecionar); retorne None para seguir o fluxo normal."),
    ("pai_list", "Depois de renderizar a página de listagem. Recebe a Response já montada; retorne uma nova Response para substituí-la, ou None para manter."),
    ("pbo_create", "Antes de exibir/processar o formulário de criação."),
    ("pai_create", "Depois que um registro é criado com sucesso."),
    ("pbo_update", "Antes de processar a edição de um registro."),
    ("pai_update", "Depois que um registro é atualizado com sucesso."),
    ("pbo_delete", "Antes de mover um registro para a lixeira ou excluir permanentemente."),
    ("pai_delete", "Depois que um registro é movido para a lixeira ou excluído permanentemente."),
]

SERVICE_HOOKS = [
    ("pbo_apply_fields", "Antes de _apply_fields() copiar o payload para o objeto. Recebe (obj, data); pode mutar `data` e retorná-lo, ou retornar None para usar o original sem mudança."),
    ("pai_apply_fields", "Depois de _apply_fields(), antes do commit. Recebe (obj, data); útil para calcular campos derivados."),
]

ROUTES_HOOKS = [
    ("pbo_list", "Antes de processar GET / (listagem via API)."),
    ("pai_list", "Depois de montar a resposta JSON de listagem. Recebe o dict de resposta; retorne um novo dict para substituí-lo, ou None para manter."),
    ("pbo_create", "Antes de processar POST / (criação via API). Recebe o payload recebido; pode mutar e retornar, ou None."),
    ("pai_create", "Depois que um registro é criado com sucesso via API."),
    ("pbo_update", "Antes de processar PUT/PATCH /<id> (edição via API)."),
    ("pai_update", "Depois que um registro é atualizado com sucesso via API."),
    ("pbo_delete", "Antes de processar trash/delete via API."),
    ("pai_delete", "Depois que um registro é removido/movido para lixeira via API."),
]


def _stub_content(class_name: str, layer_label: str, hooks: list[tuple[str, str]]) -> str:
    lines = [
        f'"""',
        f"Hooks de {layer_label} para {class_name}.",
        "",
        "Este arquivo é criado UMA VEZ pelo gerador e nunca mais sobrescrito,",
        "mesmo com --overwrite. Edite livremente — é seu espaço de customização.",
        "",
        "Cada função abaixo é opcional: se você não precisar de um hook,",
        "pode deixar a função retornando None (comportamento padrão, sem",
        "efeito) ou remover a função inteira — a ausência da função é",
        "tratada exatamente como retornar None.",
        '"""',
        "",
    ]
    for name, doc in hooks:
        lines.append(f"def {name}(*args, **kwargs):")
        lines.append(f'    """{doc}"""')
        lines.append("    return None")
        lines.append("")
    return "\n".join(lines)


def ensure_hooks_file(output_dir: Path, class_name: str, file_stem: str,
                       layer_label: str, hooks: list[tuple[str, str]]) -> bool:
    """
    Cria <file_stem>_hooks.py em output_dir SE ainda não existir.
    Retorna True se criou, False se já existia (nada foi tocado).
    """
    path = output_dir / f"{file_stem}_hooks.py"
    if path.exists():
        return False
    path.write_text(_stub_content(class_name, layer_label, hooks), encoding="utf-8")
    return True
