# utils/smart_list/builder.py
from __future__ import annotations

from typing import List, Type, Any, Optional
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import ColumnProperty

from utils.smart_list.config import FilterDef


def build_filters_from_model(
    model_class: Type,
    *,
    include_enum: bool = True,
    include_fk: bool = True,  # por padrão gera filtro para FK
) -> List[FilterDef]:
    """
    Gera automaticamente FilterDef a partir das colunas do model SQLAlchemy.

    - Para colunas do tipo Enum: cria FilterDef com type='select' e options extraídas
      do próprio Enum (usa a classe enum guardada no tipo da coluna).
    - Para colunas FK: se include_fk=True, cria FilterDef com type='text' e placeholder
      genérico (ou pode criar um tipo especial 'fk' para ser tratado pelo renderer).
    - Demais colunas não são convertidas automaticamente para evitar poluição visual.

    A função também pode ser estendida para ler as anotações @listview.filters
    (definidas no model com `Filter`), mas isso é opcional.

    Args:
        model_class: Classe do model (ex: Book, Loan).
        include_enum: Se True (padrão), adiciona filtros para colunas Enum.
        include_fk: Se False (padrão), ignora FKs. Se True, adiciona filtros de texto.
    Returns:
        Lista de FilterDef.
    """
    filters = []
    # [OPCIONAL] Lista de colunas a ignorar
    #IGNORED_COLUMNS = {"created_at", "updated_at", "trashed_at", "deleted_at"}
    IGNORED_COLUMNS = {}

    # Percorre todas as colunas mapeadas do model
    for prop in model_class.__mapper__.iterate_properties:
        if not isinstance(prop, ColumnProperty):
            continue

        column = prop.columns[0]
        col_name = prop.key
        col_type = column.type
        
        # [OPCIONAL] Pular colunas de auditoria
        if col_name in IGNORED_COLUMNS:
            continue        

        # --- Detecta coluna Enum (SQLAlchemy) ---
        if include_enum and isinstance(col_type, SAEnum):
            # Recupera a classe Python do Enum (ex: BookStatus)
            enum_class = col_type.enum_class
            if enum_class is not None:
                # Converte os membros do Enum para opções (value, label)
                options = [
                    (member.value, member.name.replace('_', ' ').title())
                    for member in enum_class
                ]
                label = col_name.replace('_', ' ').title()
                filters.append(
                    FilterDef(
                        name=col_name,
                        label=label,
                        type="select",
                        options=options,
                        placeholder=f"Selecione {label.lower()}",
                    )
                )
            elif col_type.enums:
                options = [(v, v.replace('_', ' ').title()) for v in col_type.enums]
                label = col_name.replace('_', ' ').title()
                filters.append(FilterDef(...))

        # --- Coluna FK (estrangeira) ---
        elif include_fk and column.foreign_keys:
            label = col_name.replace('_', ' ').title()
            # Por enquanto, cria um filtro de texto simples.
            # Futuramente, poderíamos usar type="fk" para disparar um modal.
            filters.append(
                FilterDef(
                    name=col_name,
                    label=label,
                    type="fk",  # tipo especial para ser tratado pelo renderer
                    placeholder=f"Buscar {label.lower()}...",
                )
            )

    return filters