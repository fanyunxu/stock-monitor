from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import yaml
import os

# Support environment variable overrides for Docker
db_host = os.environ.get("DATABASE_HOST", "192.168.0.12")
db_port = os.environ.get("DATABASE_PORT", "5432")
db_name = os.environ.get("DATABASE_NAME", "stock_monitor")
db_user = os.environ.get("DATABASE_USER", "xlx")
db_password = os.environ.get("DATABASE_PASSWORD", "xlx123456")

# If config.yaml exists, use it as base but allow env overrides
config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    db_config = config.get("database", {})
    db_host = os.environ.get("DATABASE_HOST", db_config.get("host", db_host))
    db_port = os.environ.get("DATABASE_PORT", db_config.get("port", db_port))
    db_name = os.environ.get("DATABASE_NAME", db_config.get("name", db_name))
    db_user = os.environ.get("DATABASE_USER", db_config.get("user", db_user))
    db_password = os.environ.get("DATABASE_PASSWORD", db_config.get("password", db_password))

DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
