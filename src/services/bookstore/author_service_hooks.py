"""
Hooks de service para Author.

Este arquivo é criado UMA VEZ pelo gerador e nunca mais sobrescrito,
mesmo com --overwrite. Edite livremente — é seu espaço de customização.

Cada função abaixo é opcional: se você não precisar de um hook,
pode deixar a função retornando None (comportamento padrão, sem
efeito) ou remover a função inteira — a ausência da função é
tratada exatamente como retornar None.
"""

def pbo_apply_fields(*args, **kwargs):
    """Antes de _apply_fields() copiar o payload para o objeto. Recebe (obj, data); pode mutar `data` e retorná-lo, ou retornar None para usar o original sem mudança."""
    return None

def pai_apply_fields(*args, **kwargs):
    """Depois de _apply_fields(), antes do commit. Recebe (obj, data); útil para calcular campos derivados."""
    return None
