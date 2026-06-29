from app.config.settings import settings
from app.database.session import SessionLocal
from app.models.rbac import Permission, Role, User
from app.shared.logging import get_logger
from app.shared.security import hash_password

logger = get_logger("seed")

MODULE_ACTIONS: dict[str, list[str]] = {
    "dashboard": ["view"],
    "youtube_extractor": ["view", "create", "update", "delete", "execute", "export"],
    "ncert": ["view", "execute", "delete"],
    "documents": ["view", "execute", "delete"],
    "knowledge": ["view", "execute"],
    "users": ["view", "create", "update", "delete"],
    "roles": ["view", "create", "update", "delete"],
    "settings": ["view", "update"],
}


def seed() -> None:
    db = SessionLocal()
    try:
        existing = {p.code for p in db.query(Permission).all()}
        for module, actions in MODULE_ACTIONS.items():
            for action in actions:
                code = f"{module}:{action}"
                if code not in existing:
                    db.add(
                        Permission(
                            module=module,
                            action=action,
                            code=code,
                            description=f"{action.title()} {module.replace('_', ' ')}",
                        )
                    )
        db.commit()

        role = db.query(Role).filter(Role.name == "Super Admin").first()
        if not role:
            role = Role(name="Super Admin", description="Full system access", is_system=True)
            db.add(role)
            db.commit()
        role.permissions = db.query(Permission).all()
        db.commit()

        admin = db.query(User).filter(User.username == settings.admin_username).first()
        if not admin:
            admin = User(
                username=settings.admin_username,
                email=settings.admin_email,
                full_name="System Administrator",
                hashed_password=hash_password(settings.admin_password),
                is_active=True,
                is_superuser=True,
                role_id=role.id,
            )
            db.add(admin)
            db.commit()
            logger.info("Seeded admin user '%s'", settings.admin_username)
    finally:
        db.close()
