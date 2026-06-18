"""
utils/validators.py — Validadores reaproveitáveis de formato/documento.

Mantido fora de annotations/__init__.py propositalmente: validações de
formato de documento (CPF, CNPJ, etc.) são lógica de domínio brasileiro,
não um conceito genérico de anotação de model. Models que precisarem
validar CPF chamam validate_cpf() dentro de um @required customizado ou
na camada de serviço — este módulo só fornece a função pura.
"""
from __future__ import annotations

import re


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF pelo algoritmo oficial dos dois dígitos verificadores.
    Aceita com ou sem máscara (000.000.000-00 ou 00000000000).

    Retorna False para:
    - tamanho diferente de 11 dígitos
    - sequências repetidas (111.111.111-11, 000.000.000-00, etc.) —
      matematicamente "válidas" pelo algoritmo, mas sempre fraudulentas
    - dígitos verificadores incorretos
    """
    digits = only_digits(cpf)

    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    def _check_digit(slice_digits: str, weight_start: int) -> int:
        total = sum(int(d) * w for d, w in zip(slice_digits, range(weight_start, 1, -1)))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first_check = _check_digit(digits[:9], 10)
    if first_check != int(digits[9]):
        return False

    second_check = _check_digit(digits[:10], 11)
    if second_check != int(digits[10]):
        return False

    return True


def format_cpf(cpf: str) -> str:
    """Formata 11 dígitos como 000.000.000-00. Retorna o original se inválido em tamanho."""
    digits = only_digits(cpf)
    if len(digits) != 11:
        return cpf
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def validate_cep(cep: str) -> bool:
    """Valida apenas o formato (8 dígitos) — CEP não tem dígito verificador."""
    return len(only_digits(cep)) == 8


def format_cep(cep: str) -> str:
    digits = only_digits(cep)
    if len(digits) != 8:
        return cep
    return f"{digits[0:5]}-{digits[5:8]}"
