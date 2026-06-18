"""
Hooks de routes (API) para Author.

Este arquivo é criado UMA VEZ pelo gerador e nunca mais sobrescrito,
mesmo com --overwrite. Edite livremente — é seu espaço de customização.

Cada função abaixo é opcional: se você não precisar de um hook,
pode deixar a função retornando None (comportamento padrão, sem
efeito) ou remover a função inteira — a ausência da função é
tratada exatamente como retornar None.
"""

def pbo_list(*args, **kwargs):
    """Antes de processar GET / (listagem via API)."""
    return None

def pai_list(*args, **kwargs):
    """Depois de montar a resposta JSON de listagem. Recebe o dict de resposta; retorne um novo dict para substituí-lo, ou None para manter."""
    return None

def pbo_create(*args, **kwargs):
    """Antes de processar POST / (criação via API). Recebe o payload recebido; pode mutar e retornar, ou None."""
    return None

def pai_create(*args, **kwargs):
    """Depois que um registro é criado com sucesso via API."""
    return None

def pbo_update(*args, **kwargs):
    """Antes de processar PUT/PATCH /<id> (edição via API)."""
    return None

def pai_update(*args, **kwargs):
    """Depois que um registro é atualizado com sucesso via API."""
    return None

def pbo_delete(*args, **kwargs):
    """Antes de processar trash/delete via API."""
    return None

def pai_delete(*args, **kwargs):
    """Depois que um registro é removido/movido para lixeira via API."""
    return None
