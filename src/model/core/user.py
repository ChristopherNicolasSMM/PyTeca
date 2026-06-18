"""
Sistema de autenticação
"""

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from werkzeug.security import check_password_hash, generate_password_hash
from annotations import display_field
from db.database import db

@display_field("username")
class User(UserMixin, db.Model):
    """Modelo de usuário para autenticação"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # ── Identidade (obrigatórios) ───────────────────────────────────────────
    # `nome` já era usado em todo o projeto como nickname/nome de exibição
    # curto (header, saudações) — mantido o mesmo nome de coluna para não
    # quebrar nenhum template ou serviço existente.
    nome = Column(String(120), nullable=False)               # nickname
    nome_completo = Column(String(255), nullable=False)        # nome completo
    celular = Column(String(20), nullable=False)               # obrigatório (diferente de `telefone`, que é opcional/fixo)

    # ── Identidade (opcionais) ───────────────────────────────────────────────
    cpf = Column(String(14), unique=True, nullable=True)        # formatado: 000.000.000-00; validado via utils.validators

    # ── Endereço completo (opcional, campos separados) ─────────────────────
    endereco_rua = Column(String(255), nullable=True)
    endereco_numero = Column(String(20), nullable=True)
    endereco_complemento = Column(String(120), nullable=True)
    endereco_bairro = Column(String(120), nullable=True)
    endereco_cidade = Column(String(120), nullable=True)
    endereco_uf = Column(String(2), nullable=True)
    endereco_cep = Column(String(10), nullable=True)

    # ── Campos de perfil (já existentes, sem alteração) ─────────────────────
    empresa = Column(String(255))
    cargo = Column(String(255))
    pais = Column(String(120))
    endereco = Column(String(255))  # legado — mantido por compatibilidade; novo cadastro usa os campos separados acima
    telefone = Column(String(50))
    sobre = Column(Text)
    twitter = Column(String(255))
    facebook = Column(String(255))
    instagram = Column(String(255))
    linkedin = Column(String(255))
    foto_perfil = Column(String(255))  # caminho relativo em static
    # Configurações de notificação
    notificacao_alteracoes = Column(Boolean, default=False)
    notificacao_novos_produtos = Column(Boolean, default=False)
    notificacao_ofertas = Column(Boolean, default=False)
    # Preferências de tema
    modo_escuro = Column(Boolean, default=False)
    # dentro da classe User
    roles = db.relationship("Role", secondary="user_roles", back_populates="users")    

    # No seu models.py
    @property
    def foto_url(self):
        if self.foto_perfil:
            return self.foto_perfil.replace("\\", "/")
        return "img/foto-padrao-perfil.png"

    def set_password(self, password):
        """Define a senha do usuário"""
        self.password_hash = generate_password_hash(password)

    def set_cpf(self, cpf: str | None) -> None:
        """
        Define o CPF já validando o dígito verificador e normalizando
        o formato. Lança ValueError se o CPF for inválido — a camada
        de serviço deve capturar isso e devolver um erro 422 amigável,
        nunca deixar propagar como 500.
        """
        from utils.validators import validate_cpf, format_cpf

        if not cpf:
            self.cpf = None
            return
        if not validate_cpf(cpf):
            raise ValueError("CPF inválido.")
        self.cpf = format_cpf(cpf)

    @property
    def endereco_completo(self) -> str:
        """Endereço formatado para exibição — usa os campos separados."""
        if not self.endereco_rua:
            return "—"
        parts = [self.endereco_rua]
        if self.endereco_numero:
            parts.append(f"nº {self.endereco_numero}")
        if self.endereco_complemento:
            parts.append(self.endereco_complemento)
        line1 = ", ".join(parts)
        line2_parts = [p for p in [self.endereco_bairro, self.endereco_cidade, self.endereco_uf] if p]
        line2 = " - ".join(line2_parts)
        cep = f"CEP {self.endereco_cep}" if self.endereco_cep else ""
        return " | ".join(p for p in [line1, line2, cep] if p)

    def check_password(self, password):
        """Verifica se a senha está correta"""
        return check_password_hash(self.password_hash, password)

    # Propriedades auxiliares compatíveis com rotas existentes
    @property
    def password(self):
        raise AttributeError("password is write-only")

    @password.setter
    def password(self, password: str):
        self.set_password(password)

    def verify_password(self, password: str) -> bool:
        return self.check_password(password)
    
    def has_permission(self, permission_name):
        # is_admin é tratado como "tem todas as permissões" (fix18) —
        # único ponto de decisão de autorização, sem caminhos paralelos.
        if self.is_admin:
            return True
        for role in self.roles:
            for perm in role.permissions:
                if perm.name == permission_name:
                    return True
        return False
    

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "nome": self.nome,
            "nome_completo": self.nome_completo,
            "celular": self.celular,
            "cpf": self.cpf,
            "endereco_rua": self.endereco_rua,
            "endereco_numero": self.endereco_numero,
            "endereco_complemento": self.endereco_complemento,
            "endereco_bairro": self.endereco_bairro,
            "endereco_cidade": self.endereco_cidade,
            "endereco_uf": self.endereco_uf,
            "endereco_cep": self.endereco_cep,
            "empresa": self.empresa,
            "cargo": self.cargo,
            "pais": self.pais,
            "endereco": self.endereco,
            "telefone": self.telefone,
            "sobre": self.sobre,
            "twitter": self.twitter,
            "facebook": self.facebook,
            "instagram": self.instagram,
            "linkedin": self.linkedin,
            "foto_perfil": self.foto_perfil,
            "notificacao_alteracoes": self.notificacao_alteracoes,
            "notificacao_novos_produtos": self.notificacao_novos_produtos,
            "notificacao_ofertas": self.notificacao_ofertas,
            "modo_escuro": self.modo_escuro,
        }

    def __repr__(self):
        return f"<User {self.username}>"


class RegistrationRequest(db.Model):
    """Modelo para solicitações de registro"""

    __tablename__ = "registration_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    company = Column(String(100), nullable=True)
    experience = Column(
        String(50), nullable=True
    )  # beginner, hobbyist, professional, brewer, other
    presentation = Column(Text, nullable=False)
    objectives = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    submitted_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, nullable=True)  # ID do admin que revisou
    notes = Column(Text, nullable=True)  # Notas do administrador

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
