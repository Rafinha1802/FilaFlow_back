import logging
from sqlalchemy import text
from app.core.database import engine
from app.core.security import get_password_hash

logger = logging.getLogger("filaflow.migrations")

def run_migrations():
    """Executa migrações automáticas e seguras no banco de dados SQLite."""
    default_hash = get_password_hash("123456")
    
    with engine.begin() as conn:
        tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        
        # 1. Tabela companies
        if "companies" in tables:
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(companies)")).fetchall()]
            if "hashed_password" not in cols:
                logger.info("Migração: Adicionando coluna 'hashed_password' à tabela 'companies'...")
                conn.execute(text("ALTER TABLE companies ADD COLUMN hashed_password VARCHAR"))
            
            conn.execute(
                text("UPDATE companies SET hashed_password = :hash WHERE hashed_password IS NULL OR hashed_password = ''"),
                {"hash": default_hash}
            )

        # 2. Tabela reception_patients
        if "reception_patients" in tables:
            cols_rec = [row[1] for row in conn.execute(text("PRAGMA table_info(reception_patients)")).fetchall()]
            if "company_id" not in cols_rec:
                logger.info("Migração: Adicionando coluna 'company_id' à tabela 'reception_patients'...")
                conn.execute(text("ALTER TABLE reception_patients ADD COLUMN company_id VARCHAR DEFAULT 'clinica-vida'"))
            
            conn.execute(
                text("UPDATE reception_patients SET company_id = 'clinica-vida' WHERE company_id IS NULL OR company_id = ''")
            )

        # 3. Tabela tickets: timestamps de atendimento real
        if "tickets" in tables:
            cols_tkt = [row[1] for row in conn.execute(text("PRAGMA table_info(tickets)")).fetchall()]
            if "started_at" not in cols_tkt:
                logger.info("Migração: Adicionando coluna 'started_at' à tabela 'tickets'...")
                conn.execute(text("ALTER TABLE tickets ADD COLUMN started_at DATETIME"))
            if "finished_at" not in cols_tkt:
                logger.info("Migração: Adicionando coluna 'finished_at' à tabela 'tickets'...")
                conn.execute(text("ALTER TABLE tickets ADD COLUMN finished_at DATETIME"))
            if "actual_duration_min" not in cols_tkt:
                logger.info("Migração: Adicionando coluna 'actual_duration_min' à tabela 'tickets'...")
                conn.execute(text("ALTER TABLE tickets ADD COLUMN actual_duration_min INTEGER"))

        # 4. Tabela subscription_orders: campos de gateway e pix
        if "subscription_orders" in tables:
            cols_ord = [row[1] for row in conn.execute(text("PRAGMA table_info(subscription_orders)")).fetchall()]
            if "pix_code" not in cols_ord:
                logger.info("Migração: Adicionando coluna 'pix_code' à tabela 'subscription_orders'...")
                conn.execute(text("ALTER TABLE subscription_orders ADD COLUMN pix_code TEXT"))
            if "pix_qr_code_base64" not in cols_ord:
                logger.info("Migração: Adicionando coluna 'pix_qr_code_base64' à tabela 'subscription_orders'...")
                conn.execute(text("ALTER TABLE subscription_orders ADD COLUMN pix_qr_code_base64 TEXT"))
            if "gateway" not in cols_ord:
                logger.info("Migração: Adicionando coluna 'gateway' à tabela 'subscription_orders'...")
                conn.execute(text("ALTER TABLE subscription_orders ADD COLUMN gateway VARCHAR DEFAULT 'mercadopago'"))
            if "paid_at" not in cols_ord:
                logger.info("Migração: Adicionando coluna 'paid_at' à tabela 'subscription_orders'...")
                conn.execute(text("ALTER TABLE subscription_orders ADD COLUMN paid_at DATETIME"))
            
    logger.info("Migrações concluídas com sucesso.")
