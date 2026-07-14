"""Seeds an initial admin user and a couple of base-data records.
Run with: python -m app.seed
"""
from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.auth import hash_password
from app.models.system import User, ProductCategory, MaterialCategory, ProcessLibraryItem

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if not db.query(User).filter(User.username == "admin").first():
        db.add(
            User(
                username="admin",
                hashed_password=hash_password("admin123"),
                full_name="Administrator",
                role="admin",
            )
        )
    if not db.query(ProductCategory).first():
        db.add_all([ProductCategory(name="Furniture"), ProductCategory(name="Textiles")])
    if not db.query(MaterialCategory).first():
        db.add_all([MaterialCategory(name="Fabric"), MaterialCategory(name="Hardware")])
    if not db.query(ProcessLibraryItem).first():
        db.add_all(
            [
                ProcessLibraryItem(name="Cutting", description="Material cutting process"),
                ProcessLibraryItem(name="Sewing", description="Assembly/sewing process"),
            ]
        )
    db.commit()
    print("Seed complete. Login with admin / admin123")
finally:
    db.close()
