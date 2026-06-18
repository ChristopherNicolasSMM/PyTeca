"""
Hooks de controller para Book.

Este arquivo é criado UMA VEZ pelo gerador e nunca mais sobrescrito,
mesmo com --overwrite. Edite livremente — é seu espaço de customização.

Cada função abaixo é opcional: se você não precisar de um hook,
pode deixar a função retornando None (comportamento padrão, sem
efeito) ou remover a função inteira — a ausência da função é
tratada exatamente como retornar None.
"""

def pbo_list(*args, **kwargs):
    """Antes de montar a query de listagem. Retorne uma Response para interceptar totalmente (ex: redirecionar); retorne None para seguir o fluxo normal."""
    return None

def pai_list(*args, **kwargs):
    """Depois de renderizar a página de listagem. Recebe a Response já montada; retorne uma nova Response para substituí-la, ou None para manter."""
    return None

def pbo_create(*args, **kwargs):
    """Antes de exibir/processar o formulário de criação."""
    return None

def pai_create(*args, **kwargs):
    """Depois que um registro é criado com sucesso."""
    return None

def pbo_update(*args, **kwargs):
    """Antes de processar a edição de um registro."""
    return None

def pai_update(*args, **kwargs):
    """Depois que um registro é atualizado com sucesso."""
    return None

def pbo_delete(*args, **kwargs):
    """Antes de mover um registro para a lixeira ou excluir permanentemente."""
    return None

def pai_delete(*args, **kwargs):
    """Depois que um registro é movido para a lixeira ou excluído permanentemente."""
    return None
