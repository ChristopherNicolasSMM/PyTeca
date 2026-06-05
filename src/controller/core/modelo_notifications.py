# Em qualquer lugar do seu código, você pode criar notificações assim:
def create_user_notification(
    user_id,
    title,
    message,
    notification_type="info",
    action_url=None,
    action_params=None,
    icon="bi-bell",
    priority=0,
):
    """Função helper para criar notificações"""
    from db.database import db
    from model.core.notification import Notification

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_params=action_params,
        icon=icon,
        priority=priority,
    )

    db.session.add(notification)
    db.session.commit()

    return notification


# Exemplos de uso:
# create_user_notification(
#     user_id=1,
#     title="Novo Dispositivo Conectado",
#     message="iSpindel-01 conectou-se ao sistema",
#     notification_type="success",
#     action_url="/dispositivos",
#     action_params={"device_id": 123},
#     icon="bi-wifi",
#     priority=1
# )
