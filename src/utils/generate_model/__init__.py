# utils/generate_model/__init__.py
"""
Pacote de geração automática de CRUD a partir de modelos anotados.

Estrutura:
    config.yaml              — configuração dos modelos a gerar e opções
    template_loader.py       — carrega e renderiza templates .j2
    templates/
        standard/            — tema padrão (entregue com o projeto)
            controller.py.j2
            service.py.j2
            routes.py.j2
            manage.html.j2
            detail.html.j2
            form_modal.html.j2
        <seu_tema>/          — tema personalizado (configure via template_theme no YAML)
"""

__version__ = "0.2.0"
