# routes/main_routes.py
import logging
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from db.database import db
from model.user import RegistrationRequest

# Tentar importar flask_mail (opcional)
try:
    from flask_mail import Mail, Message

    MAIL_AVAILABLE = True
except ImportError:
    MAIL_AVAILABLE = False
    Message = None
    Mail = None

register_bp = Blueprint("register", __name__)


@register_bp.route("/register/request", methods=["POST"])
def api_register_request():
    """API para processar solicitação de registro"""
    try:
        data = request.get_json()

        # Validar dados obrigatórios
        required_fields = ["first_name", "last_name", "email", "presentation", "terms"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Campo {field} é obrigatório"}), 400

        # Verificar se já existe solicitação com este e-mail
        existing_request = RegistrationRequest.query.filter_by(
            email=data["email"]
        ).first()
        if existing_request:
            return (
                jsonify(
                    {"error": "Já existe uma solicitação pendente com este e-mail"}
                ),
                400,
            )

        # Criar registro da solicitação
        registration_request = RegistrationRequest(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            phone=data.get("phone", ""),
            company=data.get("company", ""),
            experience=data.get("experience", ""),
            presentation=data["presentation"],
            objectives=data.get("objectives", ""),
            status="pending",
            submitted_at=datetime.utcnow(),
        )

        db.session.add(registration_request)
        db.session.commit()

        # Enviar e-mail para o administrador (se disponível)
        if MAIL_AVAILABLE:
            try:
                send_registration_email(registration_request)
            except Exception as e:
                logging.error(f"Erro ao enviar e-mail: {e}")
                # Não falha a solicitação se o e-mail não for enviado

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Solicitação enviada com sucesso! Entraremos em contato em breve.",
                    "request_id": registration_request.id,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro na solicitação de registro: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500


def send_registration_email(registration_request):
    """Envia e-mail para o administrador sobre nova solicitação"""
    if not MAIL_AVAILABLE:
        logging.warning("Flask-Mail não está disponível. E-mail não será enviado.")
        return

    mail = Mail(current_app)

    subject = f"Nova Solicitação de Registro - {registration_request.first_name} {registration_request.last_name}"

    # Corpo do e-mail em HTML
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #f8f9fa; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .field {{ margin-bottom: 10px; }}
            .label {{ font-weight: bold; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Nova Solicitação de Registro</h2>
            </div>
            <div class="content">
                <div class="field">
                    <span class="label">Nome:</span> {registration_request.first_name} {registration_request.last_name}
                </div>
                <div class="field">
                    <span class="label">E-mail:</span> {registration_request.email}
                </div>
                <div class="field">
                    <span class="label">Telefone:</span> {registration_request.phone or 'Não informado'}
                </div>
                <div class="field">
                    <span class="label">Empresa:</span> {registration_request.company or 'Não informado'}
                </div>
                <div class="field">
                    <span class="label">Experiência:</span> {registration_request.experience or 'Não informado'}
                </div>
                <div class="field">
                    <span class="label">Apresentação:</span><br>
                    {registration_request.presentation}
                </div>
                <div class="field">
                    <span class="label">Objetivos:</span><br>
                    {registration_request.objectives or 'Não informado'}
                </div>
                <div class="field">
                    <span class="label">Data de Solicitação:</span> {registration_request.submitted_at.strftime('%d/%m/%Y %H:%M')}
                </div>
            </div>
            <div class="footer">
                <p>ID da Solicitação: {registration_request.id}</p>
                <p>Este é um e-mail automático do sistema BrewStation.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Corpo do e-mail em texto simples
    text_body = f"""
    Nova Solicitação de Registro
    
    Nome: {registration_request.first_name} {registration_request.last_name}
    E-mail: {registration_request.email}
    Telefone: {registration_request.phone or 'Não informado'}
    Empresa: {registration_request.company or 'Não informado'}
    Experiência: {registration_request.experience or 'Não informado'}
    
    Apresentação:
    {registration_request.presentation}
    
    Objetivos:
    {registration_request.objectives or 'Não informado'}
    
    Data: {registration_request.submitted_at.strftime('%d/%m/%Y %H:%M')}
    ID: {registration_request.id}
    """

    # Obter e-mail do admin das configurações
    admin_email = current_app.config.get("ADMIN_EMAIL", "admin@brewstation.com")

    msg = Message(
        subject=subject, recipients=[admin_email], html=html_body, body=text_body
    )

    mail.send(msg)
