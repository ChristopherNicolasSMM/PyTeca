# utils/generate_from_model.py
import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional

from annotations import get_model_metadata, plural

# ============================================================
# CARREGAMENTO DE CONFIGURAÇÃO YAML
# ============================================================
def load_config(config_path: str = "utils/generate_model/config.yaml") -> Dict:
    """Carrega o arquivo de configuração YAML."""
    import yaml
    config_file = Path(__file__).parent / "generate_model" / "config.yaml"
    if not config_file.exists():
        print(f"Arquivo de configuração não encontrado: {config_file}")
        return {}
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# ============================================================
# CARREGAMENTO DE CLASSES DO ARQUIVO MODEL
# ============================================================
def load_classes_from_file(file_path: str, class_name: Optional[str] = None) -> List[tuple]:
    """
    Carrega todas as classes de um arquivo Python que são subclasses de db.Model
    e que não contenham 'Trash' no nome.
    Retorna lista de (cls, nome_da_classe).
    """
    spec = importlib.util.spec_from_file_location("temp_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    classes = []
    for name, obj in module.__dict__.items():
        if not isinstance(obj, type):
            continue
        if 'Trash' in name:
            continue
        # Verifica se é uma classe SQLAlchemy Model
        is_model = False
        if hasattr(obj, '__tablename__'):
            is_model = True
        elif hasattr(obj, '__bases__'):
            for base in obj.__bases__:
                if hasattr(base, '__name__') and base.__name__ == 'Model':
                    is_model = True
                    break
        if not is_model:
            continue
        if class_name and name != class_name:
            continue
        classes.append((obj, name))

    return classes

# ============================================================
# TEMPLATES (strings baseadas nos arquivos do projeto)
# ============================================================
def render_controller_template(class_name: str, plural: str, metadata: Dict) -> str:
    """Gera o controller baseado no template do book."""
    cols = _gen_columns(metadata)
    filters = _gen_filters(metadata)
    default_sort = metadata.get('ui_listview', {}).get('default_sort', 'id')
    label = metadata.get('label', class_name)
    module_name = metadata.get('module_name', class_name.lower())
    return f'''from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from model.{module_name} import {class_name}, {class_name}Status
from model.user_layout_pref import UserLayoutPref
from services.{class_name.lower()}.{class_name.lower()}_service import {class_name}Service
from utils.smart_list import ColumnDef, FilterDef, SmartListConfig, SmartListRenderer
from utils.smart_list.export import export_csv, export_excel, export_pdf

bp = Blueprint("{plural}", __name__, url_prefix="/{plural}")

# ---- Configuração SmartList ----
def _genre_options():
    return [("", "Todos")]

SMART_LIST_CONFIG = SmartListConfig(
    list_id="{plural}",
    endpoint="{plural}.list",
    columns=[
        {cols}
    ],
    filters=[
        {filters}
    ],
    default_sort="{default_sort}",
    default_dir="asc",
    page_sizes=[10, 20, 50, 100],
    default_page_size=20,
    exportable=True,
    export_filename="{plural}",
)

@bp.route("/")
@login_required
def list():
    status = request.args.get("status", "{class_name}Status.ACTIVE")
    export = request.args.get("export", "")

    user_layout = None
    if current_user.is_authenticated:
        pref = UserLayoutPref.get_for_user(current_user.id, SMART_LIST_CONFIG.list_id)
        if pref:
            user_layout = pref.layout

    per_page = int(request.args.get(
        "per_page",
        (user_layout or {{}}).get("per_page", SMART_LIST_CONFIG.default_page_size),
    ))

    service = {class_name}Service()
    result = service.list(
        page=int(request.args.get("page", 1)),
        per_page=per_page,
        status=status,
        search=request.args.get("search", "").strip() or None,
        genre=request.args.get("genre", "").strip() or None,
        sort=request.args.get("sort", SMART_LIST_CONFIG.default_sort),
        direction=request.args.get("dir", SMART_LIST_CONFIG.default_dir),
    )

    if export in ("csv", "excel", "pdf"):
        all_result = service.list(page=1, per_page=10_000, status=status, ...)
        visible_cols = (user_layout or {{}}).get("columns") or None
        if export == "csv":
            return export_csv(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "excel":
            return export_excel(SMART_LIST_CONFIG, all_result.items, visible_cols)
        if export == "pdf":
            return export_pdf(SMART_LIST_CONFIG, all_result.items, visible_cols, title="{label}s")

    renderer = SmartListRenderer(SMART_LIST_CONFIG)
    sl = renderer.build_context(
        items=result.items,
        total=result.total,
        pages=result.pages,
        user_layout=user_layout,
    )

    return render_template(
        "{plural}/manage.html",
        sl=sl,
        counts=service.count_by_status(),
        current_status=status,
    )

@bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    service = {class_name}Service()
    item = service.get_by_id(item_id)
    if not item:
        abort(404)
    return render_template("{plural}/detail.html", {class_name.lower()}=item)
'''

def _gen_columns(metadata):
    cols = metadata.get('ui_listview', {}).get('columns', [])
    lines = []
    for c in cols:
        name = c['name']
        label = c.get('label', name)
        sortable = 'True' if c.get('sortable') else 'False'
        width = c.get('width', 'None')
        align = c.get('align', 'start')
        if width != 'None':
            width = f'"{width}"'
        lines.append(f'        ColumnDef("{name}", "{label}", sortable={sortable}, width={width}, align="{align}")')
    return ",\n".join(lines) if lines else 'ColumnDef("id", "ID", sortable=True)'

def _gen_filters(metadata):
    filters = metadata.get('ui_listview', {}).get('filters', [])
    lines = []
    for f in filters:
        name = f['name']
        ftype = f.get('type', 'text')
        placeholder = f.get('placeholder', '')
        if placeholder:
            placeholder = f', placeholder="{placeholder}"'
        else:
            placeholder = ''
        lines.append(f'        FilterDef("{name}", "{f.get("label", name)}", type="{ftype}"{placeholder})')
    return ",\n".join(lines) if lines else 'FilterDef("search", "Buscar", type="text")'

def render_service_template(class_name: str, metadata: Dict) -> str:
    """Gera o service baseado no book_service.py."""
    module_name = metadata.get('module_name', class_name.lower())
    return f'''from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from db.database import db
from model.{module_name} import {class_name}, {class_name}Status


@dataclass
class {class_name}ListResult:
    items: list[{class_name}]
    total: int
    page: int
    per_page: int
    pages: int


@dataclass
class ServiceResult:
    success: bool
    data: Any = None
    error: str | None = None
    code: int = 200


class {class_name}Service:
    """Camada de negócio para {class_name.lower()}."""

    def list(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str = {class_name}Status.ACTIVE,
        search: str | None = None,
        genre: str | None = None,
        sort: str = "id",
        direction: str = "asc",
    ) -> {class_name}ListResult:
        query = {class_name}.query
        if status != "all":
            query = query.filter({class_name}.status == status)
        if search:
            pattern = f"%{{search.strip()}}%"
            query = query.filter({class_name}.name.ilike(pattern))
        if genre:
            query = query.filter({class_name}.genre.ilike(f"%{{genre}}%"))
        sort_col = getattr({class_name}, sort, {class_name}.id)
        query = query.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return {class_name}ListResult(
            items=pagination.items,
            total=pagination.total,
            page=page,
            per_page=per_page,
            pages=pagination.pages,
        )

    def get_by_id(self, id: int) -> {class_name} | None:
        return db.session.get({class_name}, id)

    def create_draft(self) -> ServiceResult:
        obj = {class_name}(status={class_name}Status.DRAFT)
        db.session.add(obj)
        db.session.commit()
        return ServiceResult(success=True, data=obj, code=201)

    def publish_draft(self, id: int, data: dict | None = None) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != {class_name}Status.DRAFT:
            return ServiceResult(success=False, error="Rascunho não encontrado", code=404)
        if data:
            self._apply_fields(obj, data)
        obj.status = {class_name}Status.ACTIVE
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def update(self, id: int, data: dict) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado", code=404)
        self._apply_fields(obj, data)
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def trash(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj:
            return ServiceResult(success=False, error="Registro não encontrado", code=404)
        obj.status = {class_name}Status.TRASH
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def restore(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != {class_name}Status.TRASH:
            return ServiceResult(success=False, error="Registro não está na lixeira", code=404)
        obj.status = {class_name}Status.ACTIVE
        db.session.commit()
        return ServiceResult(success=True, data=obj)

    def delete_permanent(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != {class_name}Status.TRASH:
            return ServiceResult(success=False, error="Apenas registros na lixeira podem ser excluídos", code=400)
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={{"id": id}})

    def discard_draft(self, id: int) -> ServiceResult:
        obj = self.get_by_id(id)
        if not obj or obj.status != {class_name}Status.DRAFT:
            return ServiceResult(success=False, error="Apenas rascunhos podem ser descartados", code=400)
        db.session.delete(obj)
        db.session.commit()
        return ServiceResult(success=True, data={{"id": id}})

    def _apply_fields(self, obj: {class_name}, data: dict) -> None:
        for key, value in data.items():
            if hasattr(obj, key) and value is not None:
                setattr(obj, key, value)
'''

def render_routes_template(class_name: str, plural: str, metadata: Dict) -> str:
    """Gera as rotas da API baseado no book_routes.py."""
    module_name = metadata.get('module_name', class_name.lower())
    return f'''from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.{class_name.lower()}.{class_name.lower()}_service import {class_name}Service
from model.{module_name} import {class_name}Status

bp = Blueprint("{class_name.lower()}_api", __name__, url_prefix="/api/{plural}")

def _ok(data, code: int = 200):
    return jsonify({{"success": True, "data": data}}), code

def _err(message: str, code: int = 400):
    return jsonify({{"success": False, "error": message}}), code

@bp.route("/", methods=["GET"])
@login_required
def list():
    status = request.args.get("status", {class_name}Status.ACTIVE)
    search = request.args.get("search", "").strip() or None
    genre = request.args.get("genre", "").strip() or None
    sort = request.args.get("sort", "id")
    direction = request.args.get("dir", "asc")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 20)))

    service = {class_name}Service()
    result = service.list(
        page=page, per_page=per_page, status=status,
        search=search, genre=genre, sort=sort, direction=direction,
    )
    return _ok({{
        "items": [item.to_dict() for item in result.items],
        "total": result.total,
        "page": result.page,
        "per_page": result.per_page,
        "pages": result.pages,
    }})

@bp.route("/<int:id>", methods=["GET"])
@login_required
def get(id: int):
    service = {class_name}Service()
    item = service.get_by_id(id)
    if not item:
        return _err("Não encontrado", 404)
    return _ok(item.to_dict())

@bp.route("/draft", methods=["POST"])
@login_required
def create_draft():
    service = {class_name}Service()
    result = service.create_draft()
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict(), 201)

@bp.route("/<int:id>/publish", methods=["POST"])
@login_required
def publish_draft(id: int):
    data = request.get_json(silent=True) or {{}}
    service = {class_name}Service()
    result = service.publish_draft(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())

@bp.route("/<int:id>", methods=["PUT", "PATCH"])
@login_required
def update(id: int):
    data = request.get_json(silent=True) or {{}}
    service = {class_name}Service()
    result = service.update(id, data)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())

@bp.route("/<int:id>/trash", methods=["POST"])
@login_required
def trash(id: int):
    service = {class_name}Service()
    result = service.trash(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())

@bp.route("/<int:id>/restore", methods=["POST"])
@login_required
def restore(id: int):
    service = {class_name}Service()
    result = service.restore(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data.to_dict())

@bp.route("/<int:id>", methods=["DELETE"])
@login_required
def delete_permanent(id: int):
    if not current_user.is_admin:
        return _err("Apenas administradores", 403)
    service = {class_name}Service()
    result = service.delete_permanent(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)

@bp.route("/<int:id>/discard", methods=["DELETE"])
@login_required
def discard_draft(id: int):
    service = {class_name}Service()
    result = service.discard_draft(id)
    if not result.success:
        return _err(result.error, result.code)
    return _ok(result.data)
'''

def render_manage_template(class_name: str, plural: str, metadata: Dict) -> str:
    """Template manage.html baseado em books/manage.html."""
    label = metadata.get('label', class_name)
    return f'''{{% extends "base.html" %}}
{{% from "_components/smart_list.html" import render as smart_list, scripts as sl_scripts %}}

{{% block title %}}{label}s{{% endblock %}}

{{% block content %}}
<div class="pagetitle">
  <h1>{label}s</h1>
  <nav>
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="{{{{ url_for('web.dashboard') }}}}">Home</a></li>
      <li class="breadcrumb-item active">{label}s</li>
    </ol>
  </nav>
</div>

<section class="section">
  <ul class="nav nav-tabs mb-3">
    {{% set tab_map = [
      ('active', 'bi-book', 'Publicados', counts.active | default(0)),
      ('draft',  'bi-pencil-square', 'Rascunhos', counts.draft | default(0)),
      ('trash',  'bi-trash3', 'Lixeira', counts.trash | default(0)),
    ] %}}
    {{% for value, icon, label, count in tab_map %}}
    <li class="nav-item">
      <a class="nav-link {{% if current_status == value %}}active{{% endif %}}"
         href="{{{{ url_for('{plural}.list', status=value) }}}}">
        <i class="bi {{ icon }} me-1"></i>{{ label }}
        {{% if count > 0 %}}
          <span class="badge ms-1
            {{% if value == 'trash' %}}bg-danger
            {{% elif value == 'draft' %}}bg-warning text-dark
            {{% else %}}bg-primary{{% endif %}}">
            {{{{ count }}}}
          </span>
        {{% endif %}}
      </a>
    </li>
    {{% endfor %}}
  </ul>

  <div class="card">
    <div class="card-body pt-3">
      {{% if current_status != 'trash' %}}
      <div class="d-flex justify-content-end mb-2">
        <button type="button" class="btn btn-primary btn-sm" id="btnNovo{class_name}">
          <i class="bi bi-plus-lg me-1"></i>Novo {label}
        </button>
      </div>
      {{% endif %}}

      {{% macro _row_actions(row, status=current_status) %}}
        {{% if status == 'active' %}}
          <a href="{{{{ url_for('{plural}.detail', item_id=row.id) }}}}" class="btn btn-outline-primary" title="Visualizar"><i class="bi bi-eye"></i></a>
          <button type="button" class="btn btn-outline-secondary btn-edit" data-id="{{{{ row.id }}}}" title="Editar"><i class="bi bi-pencil"></i></button>
          <form method="post" action="{{{{ url_for('{plural}.trash', {class_name.lower()}_id=row.id) }}}}" class="d-inline" onsubmit="return confirm('Mover para a lixeira?')">
            <button class="btn btn-outline-danger" title="Lixeira"><i class="bi bi-trash3"></i></button>
          </form>
        {{% elif status == 'draft' %}}
          <button type="button" class="btn btn-outline-primary btn-edit" data-id="{{{{ row.id }}}}" title="Continuar editando"><i class="bi bi-pencil"></i></button>
          <form method="post" action="{{{{ url_for('{plural}.discard_draft', {class_name.lower()}_id=row.id) }}}}" class="d-inline" onsubmit="return confirm('Descartar rascunho?')">
            <button class="btn btn-outline-danger" title="Descartar"><i class="bi bi-x-circle"></i></button>
          </form>
        {{% elif status == 'trash' %}}
          <form method="post" action="{{{{ url_for('{plural}.restore', {class_name.lower()}_id=row.id) }}}}" class="d-inline">
            <button class="btn btn-outline-success" title="Restaurar"><i class="bi bi-arrow-counterclockwise"></i></button>
          </form>
          {{% if current_user.is_admin %}}
          <form method="post" action="{{{{ url_for('{plural}.delete_permanent', {class_name.lower()}_id=row.id) }}}}" class="d-inline" onsubmit="return confirm('Excluir PERMANENTEMENTE?')">
            <button class="btn btn-danger" title="Excluir permanente"><i class="bi bi-trash3-fill"></i></button>
          </form>
          {{% endif %}}
        {{% endif %}}
      {{% endmacro %}}

      {{{{ smart_list(sl, row_actions=_row_actions) }}}}
    </div>
  </div>
</section>
{{% include "{plural}/_modals/{class_name.lower()}_form_modal.html" %}}
{{% endblock %}}

{{% block extra_js %}}
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
{{{{ sl_scripts() }}}}
<script>
  (function() {{
    const modal = new bootstrap.Modal(document.getElementById('{class_name.lower()}Modal'));
    const form = document.getElementById('{class_name.lower()}Form');
    const titleElem = document.getElementById('{class_name.lower()}ModalTitle');
    const idElem = document.getElementById('{class_name.lower()}Id');

    function resetForm() {{
      form.reset();
      idElem.value = '';
      titleElem.innerText = 'Novo {label}';
      document.getElementById('quantity') && (document.getElementById('quantity').value = 0);
      document.getElementById('available') && (document.getElementById('available').value = 0);
    }}

    async function loadData(id) {{
      try {{
        const response = await fetch(`/api/{plural}/${{id}}`);
        const result = await response.json();
        if (result.success) {{
          const data = result.data;
          for (const [key, value] of Object.entries(data)) {{
            const field = document.getElementById(key);
            if (field) field.value = value ?? '';
          }}
          idElem.value = id;
          titleElem.innerText = 'Editar {label}';
        }} else {{
          alert('Erro ao carregar dados: ' + (result.error || 'Desconhecido'));
          modal.hide();
        }}
      }} catch (err) {{
        console.error(err);
        alert('Erro de conexão.');
        modal.hide();
      }}
    }}

    async function save() {{
      const id = idElem.value;
      const data = {{}};
      const fields = form.querySelectorAll('[name]');
      fields.forEach(field => {{
        let value = field.value;
        if (field.type === 'number') value = parseInt(value) || null;
        data[field.name] = value;
      }});
      if (!data.title || !data.author) {{
        alert('Campos obrigatórios não preenchidos.');
        return;
      }}
      const saveBtn = document.getElementById('btnSave{class_name}');
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
      try {{
        let response;
        if (id) {{
          response = await fetch(`/api/{plural}/${{id}}`, {{
            method: 'PUT',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }});
        }} else {{
          const draftRes = await fetch(`/api/{plural}/draft`, {{ method: 'POST' }});
          const draftData = await draftRes.json();
          if (!draftData.success) throw new Error(draftData.error);
          const draftId = draftData.data.id;
          response = await fetch(`/api/{plural}/${{draftId}}/publish`, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data)
          }});
        }}
        const result = await response.json();
        if (result.success) {{
          modal.hide();
          window.location.reload();
        }} else {{
          alert('Erro: ' + (result.error || 'Falha ao salvar'));
        }}
      }} catch (err) {{
        console.error(err);
        alert('Erro de conexão.');
      }} finally {{
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'Salvar';
      }}
    }}

    document.getElementById('btnNovo{class_name}')?.addEventListener('click', () => {{
      resetForm();
      modal.show();
    }});
    document.getElementById('btnSave{class_name}')?.addEventListener('click', save);
    document.body.addEventListener('click', (e) => {{
      const btn = e.target.closest('.btn-edit');
      if (btn && btn.dataset.id) {{
        e.preventDefault();
        resetForm();
        loadData(btn.dataset.id);
        modal.show();
      }}
    }});
  }})();
</script>
{{% endblock %}}
'''

def render_detail_template(class_name: str, plural: str, metadata: Dict) -> str:
    """Template detail.html baseado em books/detail.html."""
    label = metadata.get('label', class_name)
    fields = metadata.get('ui_form', {}).get('fields', [])
    fields_rows = ''
    for field in fields:
        fields_rows += f'''
            <tr>
              <th style="width:30%">{field.replace('_',' ').title()}</th>
              <td>{{{{ {class_name.lower()}.{field} or '—' }}}}</td>
            </tr>'''
    return f'''{{% extends "base.html" %}}

{{% block title %}}

    {{{{ class_name.lower() }}.title}} - Detalhe do {label}{{% endblock %}}
    }}

{{% block content %}}
<div class="pagetitle">
  <h1>{{{{ {class_name.lower()}.title }}}}</h1>
  <nav>
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="{{{{ url_for('web.dashboard') }}}}">Home</a></li>
      <li class="breadcrumb-item"><a href="{{{{ url_for('{plural}.list') }}}}">{label}s</a></li>
      <li class="breadcrumb-item active">{{{{ {class_name.lower()}.title }}}}</li>
    </ol>
  </nav>
</div>

<section class="section">
  <div class="row">
    <div class="col-lg-12">
      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Informações</h5>
          <table class="table table-bordered">
            {fields_rows}
          </table>
          <div class="mt-4">
            <div class="btn-group">
              <a href="{{{{ url_for('{plural}.list') }}}}" class="btn btn-secondary">Voltar</a>
              {{% if {class_name.lower()}.status == 'active' %}}
                <button type="button" class="btn btn-primary" id="btnEdit{class_name}" data-id="{{{{ {class_name.lower()}.id }}}}">Editar</button>
                <form method="post" action="{{{{ url_for('{plural}.trash', {class_name.lower()}_id={class_name.lower()}.id) }}}}" class="d-inline" onsubmit="return confirm('Mover para lixeira?')">
                  <button type="submit" class="btn btn-outline-danger">Mover para lixeira</button>
                </form>
              {{% elif {class_name.lower()}.status == 'draft' %}}
                <button type="button" class="btn btn-primary" id="btnEdit{class_name}" data-id="{{{{ {class_name.lower()}.id }}}}">Continuar edição</button>
                <form method="post" action="{{{{ url_for('{plural}.discard_draft', {class_name.lower()}_id={class_name.lower()}.id) }}}}" class="d-inline" onsubmit="return confirm('Descartar rascunho?')">
                  <button type="submit" class="btn btn-danger">Descartar</button>
                </form>
              {{% elif {class_name.lower()}.status == 'trash' %}}
                <form method="post" action="{{{{ url_for('{plural}.restore', {class_name.lower()}_id={class_name.lower()}.id) }}}}" class="d-inline">
                  <button type="submit" class="btn btn-success">Restaurar</button>
                </form>
                {{% if current_user.is_admin %}}
                <form method="post" action="{{{{ url_for('{plural}.delete_permanent', {class_name.lower()}_id={class_name.lower()}.id) }}}}" class="d-inline" onsubmit="return confirm('Excluir permanentemente?')">
                  <button type="submit" class="btn btn-danger">Excluir permanentemente</button>
                </form>
                {{% endif %}}
              {{% endif %}}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
{{% include "{plural}/_modals/{class_name.lower()}_form_modal.html" %}}
{{% endblock %}}

{{% block extra_js %}}
<script>
  const modal = new bootstrap.Modal(document.getElementById('{class_name.lower()}Modal'));
  const editBtn = document.getElementById('btnEdit{class_name}');
  if (editBtn) {{
    editBtn.addEventListener('click', () => {{
      // O mesmo script do manage.html será reutilizado
      const loadData = (id) => {{ ... }};
      loadData(editBtn.dataset.id);
      modal.show();
    }});
  }}
</script>
{{% endblock %}}
'''

def render_modal_template(class_name: str, metadata: Dict) -> str:
    """Template do modal de formulário."""
    fields = metadata.get('ui_form', {}).get('fields', [])
    groups = metadata.get('ui_form', {}).get('groups', [])
    rows = []
    if groups:
        for group in groups:
            rows.append(f'<h6>{group["label"]}</h6>')
            for field in group['fields']:
                rows.append(f'''
          <div class="row mb-3">
            <label for="{field}" class="col-sm-2 col-form-label">{field.replace('_',' ').title()}</label>
            <div class="col-sm-10">
              <input type="text" class="form-control" id="{field}" name="{field}">
            </div>
          </div>''')
    else:
        for field in fields:
            rows.append(f'''
          <div class="row mb-3">
            <label for="{field}" class="col-sm-2 col-form-label">{field.replace('_',' ').title()}</label>
            <div class="col-sm-10">
              <input type="text" class="form-control" id="{field}" name="{field}">
            </div>
          </div>''')
    return f'''{{# Modal de formulário para {class_name} #}}
<div class="modal fade" id="{class_name.lower()}Modal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="{class_name.lower()}ModalTitle">Novo {metadata.get('label', class_name)}</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="{class_name.lower()}Form">
          <input type="hidden" id="{class_name.lower()}Id">
          {''.join(rows)}
        </form>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
        <button type="button" class="btn btn-primary" id="btnSave{class_name}">Salvar</button>
      </div>
    </div>
  </div>
</div>
'''

# ============================================================
# FUNÇÕES DE GERAÇÃO (CONTROLLER, SERVICE, ROUTES, TEMPLATES)
# ============================================================
def generate_controller(model_file: str, class_name: str, plural: str, metadata: Dict):
    base_name = Path(model_file).stem
    controller_dir = Path("src/controller") / base_name     
    controller_dir.mkdir(parents=True, exist_ok=True)
    controller_path = controller_dir / f"{class_name.lower()}.py"
    if controller_path.exists():
        print(f"Controller já existe: {controller_path}")
        return
    content = render_controller_template(class_name, plural, metadata)
    controller_path.write_text(content)
    print(f"Gerado: {controller_path}")

def generate_service(model_file: str, class_name: str, plural: str, metadata: Dict):
    base_name = Path(model_file).stem
    service_dir = Path("src/services") / base_name
    service_dir.mkdir(parents=True, exist_ok=True)
    service_path = service_dir / f"{class_name.lower()}_service.py"
    if service_path.exists():
        print(f"Service já existe: {service_path}")
        return
    content = render_service_template(class_name, metadata)
    service_path.write_text(content)
    print(f"Gerado: {service_path}")

def generate_routes(model_file: str, class_name: str, plural: str, metadata: Dict):
    base_name = Path(model_file).stem
    routes_dir = Path("src/api/routes") / base_name
    routes_dir.mkdir(parents=True, exist_ok=True)
    routes_path = routes_dir / f"{class_name.lower()}_routes.py"
    if routes_path.exists():
        print(f"Routes já existe: {routes_path}")
        return
    content = render_routes_template(class_name, plural, metadata)
    routes_path.write_text(content)
    print(f"Gerado: {routes_path}")

def generate_templates(model_file: str, class_name: str, plural: str, metadata: Dict):
    base_name = Path(model_file).stem
    templates_dir = Path("src/templates") / plural
    templates_dir.mkdir(parents=True, exist_ok=True)
    modals_dir = templates_dir / "_modals"
    modals_dir.mkdir(exist_ok=True)

    manage_path = templates_dir / "manage.html"
    if not manage_path.exists():
        manage_path.write_text(render_manage_template(class_name, plural, metadata))
        print(f"Gerado: {manage_path}")

    detail_path = templates_dir / "detail.html"
    if not detail_path.exists():
        detail_path.write_text(render_detail_template(class_name, plural, metadata))
        print(f"Gerado: {detail_path}")

    modal_path = modals_dir / f"{class_name.lower()}_form_modal.html"
    if not modal_path.exists():
        modal_path.write_text(render_modal_template(class_name, metadata))
        print(f"Gerado: {modal_path}")

# ============================================================
# ATUALIZAÇÃO DO MAIN.PY (OPCIONAL)
# ============================================================
def update_main_blueprint(class_name: str, plural: str, model_file: str):
    main_path = Path("src/main.py")
    if not main_path.exists():
        print("main.py não encontrado")
        return
    content = main_path.read_text()
    import_line = f"from controller.{Path(model_file).stem}.{class_name.lower()} import bp as {plural}_bp"
    if import_line in content:
        print(f"Blueprint {plural}_bp já registrado.")
        return
    lines = content.splitlines()
    insert_pos = -1
    for i, line in enumerate(lines):
        if line.startswith("from controller.") and "import" in line:
            insert_pos = i + 1
    if insert_pos == -1:
        for i, line in enumerate(lines):
            if "app = create_app()" in line:
                insert_pos = i
                break
    if insert_pos != -1:
        lines.insert(insert_pos, import_line)
    new_content = "\n".join(lines)
    main_path.write_text(new_content)
    print(f"main.py atualizado com import. Registre o blueprint manualmente em register_core_blueprints.")

# ============================================================
# PONTO DE ENTRADA PARA GERAÇÃO VIA CONFIG
# ============================================================
def generate_from_config():
    config = load_config()
    generator_cfg = config.get("generator", {})
    overwrite = generator_cfg.get("overwrite", False)
    for entry in config.get("models", []):
        source = entry["source"]
        class_name = entry.get("class_name")
        plural = entry.get("plural")
        file_path = Path(source)
        if not file_path.exists():
            print(f"Arquivo não encontrado: {file_path}")
            continue
        classes = load_classes_from_file(str(file_path), class_name)
        if not classes:
            print(f"Nenhuma classe encontrada em {file_path}")
            continue
        for cls, cls_name in classes:
            print(f"Gerando para classe {cls_name} do arquivo {file_path}")
            metadata = get_model_metadata(cls)
            metadata["module_name"] = file_path.stem
            if plural:
                metadata["plural"] = plural
            final_plural = metadata.get("plural", cls_name.lower() + "s")
            generate_controller(str(file_path), cls_name, final_plural, metadata)
            generate_service(str(file_path), cls_name, final_plural, metadata)
            generate_routes(str(file_path), cls_name, final_plural, metadata)
            generate_templates(str(file_path), cls_name, final_plural, metadata)
            # update_main_blueprint(cls_name, final_plural, str(file_path))

# ============================================================
# GERAÇÃO A PARTIR DE UM ÚNICO ARQUIVO MODEL
# ============================================================
def generate(model_path: str):
    """
    Gera todos os artefatos para um único arquivo de modelo.
    Exemplo: generate("model/author.py")
    """
    file_path = Path(model_path)
    if not file_path.exists():
        print(f"Arquivo não encontrado: {file_path}")
        return

    classes = load_classes_from_file(str(file_path))
    if not classes:
        print(f"Nenhuma classe (db.Model) encontrada em {file_path}")
        return

    for cls, cls_name in classes:
        print(f"Gerando para classe {cls_name} do arquivo {file_path.name}")
        metadata = get_model_metadata(cls)
        metadata["module_name"] = file_path.stem
        final_plural = metadata.get("plural", cls_name.lower() + "s")

        generate_controller(str(file_path), cls_name, final_plural, metadata)
        generate_service(str(file_path), cls_name, final_plural, metadata)
        generate_routes(str(file_path), cls_name, final_plural, metadata)
        generate_templates(str(file_path), cls_name, final_plural, metadata)
        # update_main_blueprint(cls_name, final_plural, str(file_path))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--model":
        if len(sys.argv) > 2:
            generate(sys.argv[2])
        else:
            print("Uso: python generate_from_model.py --model <caminho>")
    else:
        generate_from_config()