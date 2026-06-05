# utils/generate_model/template_loader.py
"""
Carrega templates .j2 de uma pasta configurável e os renderiza
usando um motor de substituição simples (sem dependência do Jinja2 da app).

Estrutura de pastas esperada:
    utils/generate_model/templates/
        standard/          ← pasta padrão (fallback)
            controller.py.j2
            service.py.j2
            routes.py.j2
            manage.html.j2
            detail.html.j2
            form_modal.html.j2
        meu_tema/          ← pasta customizada (configurável via YAML)
            ...

Variáveis disponíveis nos templates (passadas no contexto):
    {{ class_name }}       ex: "Author"
    {{ class_name_lower }} ex: "author"
    {{ module_name }}      ex: "author"  (nome do arquivo .py sem extensão)
    {{ plural }}           ex: "authors"
    {{ label }}            ex: "Autor"
    {{ default_sort }}     ex: "name"
    {{ columns }}          bloco já formatado com ColumnDef(...)
    {{ filters }}          bloco já formatado com FilterDef(...)
    {{ fields_rows }}      linhas <tr> para o detail.html
    {{ form_fields }}      campos <div class="mb-3"> para o modal
"""

from __future__ import annotations

import re
from pathlib import Path


# ── Diretório raiz dos templates de geração ───────────────────────────────────
_TEMPLATES_ROOT = Path(__file__).parent / "templates"
_DEFAULT_THEME  = "standard"


class TemplateLoader:
    """
    Carrega e renderiza templates .j2 de uma pasta de tema.

    Uso:
        loader = TemplateLoader(theme="standard")
        content = loader.render("controller.py.j2", context)
    """

    def __init__(self, theme: str = _DEFAULT_THEME):
        theme_path = _TEMPLATES_ROOT / theme
        if not theme_path.is_dir():
            print(f"⚠  Tema '{theme}' não encontrado em {_TEMPLATES_ROOT}. "
                  f"Usando 'standard'.")
            theme_path = _TEMPLATES_ROOT / _DEFAULT_THEME

        if not theme_path.is_dir():
            raise FileNotFoundError(
                f"Pasta de templates padrão não encontrada: {theme_path}"
            )

        self.theme_path = theme_path
        self.theme = theme

    # ── API pública ───────────────────────────────────────────────────────────

    def render(self, template_name: str, context: dict) -> str:
        """
        Lê o arquivo .j2 e substitui variáveis {{ var }} pelo valor em context.
        Suporta apenas substituição simples — não é um motor Jinja2 completo.
        """
        path = self.theme_path / template_name
        if not path.exists():
            # Tenta fallback para standard
            fallback = _TEMPLATES_ROOT / _DEFAULT_THEME / template_name
            if fallback.exists() and self.theme != _DEFAULT_THEME:
                print(f"   ↩  '{template_name}' não existe em '{self.theme}', "
                      f"usando standard.")
                path = fallback
            else:
                raise FileNotFoundError(
                    f"Template não encontrado: {path}"
                )

        raw = path.read_text(encoding="utf-8")
        return self._substitute(raw, context)

    def list_templates(self) -> list[str]:
        """Retorna os nomes de todos os templates disponíveis no tema."""
        return [f.name for f in self.theme_path.glob("*.j2")]

    # ── Motor de substituição ─────────────────────────────────────────────────

    @staticmethod
    def _substitute(template: str, context: dict) -> str:
        """
        Substitui {{ key }} pelo valor correspondente em context.
        Chaves não encontradas são mantidas intactas.
        """
        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            if key in context:
                return str(context[key])
            return match.group(0)  # mantém {{ key }} se não encontrado

        return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)


# ── Fábrica conveniente ───────────────────────────────────────────────────────

def get_loader(theme: str | None = None) -> TemplateLoader:
    """
    Retorna um TemplateLoader configurado.
    theme=None usa o padrão 'standard'.
    """
    return TemplateLoader(theme=theme or _DEFAULT_THEME)
