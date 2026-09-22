from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models.company import Company
from app.models.queue import Queue
from app.models.ticket import Ticket
from app.models.reception import ReceptionPatient
from datetime import datetime, timedelta

def seed_data():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Company).first():
            return

        # 1. Companies
        companies = [
            Company(
                id="clinica-vida",
                company_name="Clínica Vida",
                unit_name="Unidade Centro",
                category="Clínica",
                badge_color="emerald",
                address="Av. Paulista, 1000 - Bela Vista",
                avg_wait="35 min",
                room="Consultório 04",
                attendant_name="Dr. Carlos Mendes",
                email="atendimento@clinicavida.com.br",
                phone="(11) 3145-8000"
            ),
            Company(
                id="examelab",
                company_name="ExameLab Diagnósticos",
                unit_name="Shopping Plaza Sul",
                category="Laboratório",
                badge_color="blue",
                address="Praça das Flores, 45 - Térreo",
                avg_wait="12 min",
                room="Box 03",
                attendant_name="Guichê 03 - Mariana",
                email="contato@examelab.com.br",
                phone="(11) 3322-1100"
            ),
            Company(
                id="bistro",
                company_name="Dom Bistrô & Grill",
                unit_name="Praça Gastronômica",
                category="Restaurante",
                badge_color="amber",
                address="Rua Oscar Freire, 820",
                avg_wait="42 min",
                room="Salão Principal",
                attendant_name="Hostess Bianca",
                email="reservas@dombistro.com.br",
                phone="(11) 3088-9900"
            ),
            Company(
                id="barbearia-elite",
                company_name="Barbearia Dom Pedro",
                unit_name="Vila Madalena",
                category="Barbearia",
                badge_color="indigo",
                address="Rua Harmonia, 312",
                avg_wait="18 min",
                room="Cadeira 02",
                attendant_name="Mestre Rodrigo",
                email="contato@barbeariadompedro.com.br"
            ),
            Company(
                id="salao-glam",
                company_name="Studio Beleza & Arte",
                unit_name="Jardins",
                category="Salão",
                badge_color="rose",
                address="Alameda Lorena, 1400",
                avg_wait="25 min",
                room="Bancada 01",
                attendant_name="Camila Hair Stylist"
            ),
            Company(
                id="oficina-tech",
                company_name="AutoFix Assistência",
                unit_name="Av. Ibirapuera",
                category="Oficina",
                badge_color="orange",
                address="Av. Ibirapuera, 2300",
                avg_wait="30 min",
                room="Elevador 02",
                attendant_name="Engenheiro Marcelo"
            ),
            Company(
                id="cartorio-central",
                company_name="Cartório 5º Ofício de Notas",
                unit_name="Centro Cívico",
                category="Órgãos Públicos",
                badge_color="cyan",
                address="Rua São Bento, 405",
                avg_wait="15 min",
                room="Guichê 08",
                attendant_name="Escrevente Juliana"
            )
        ]
        db.add_all(companies)

        # 2. Queues
        queues = [
            Queue(
                id="clinica-vida",
                company_id="clinica-vida",
                name="Consulta Oftalmologia Geral",
                attendant_name="Dr. Carlos Mendes",
                room="Consultório 04",
                initial_wait_min=38,
                current_waiting=5
            ),
            Queue(
                id="examelab",
                company_id="examelab",
                name="Coleta de Exames de Sangue",
                attendant_name="Guichê 03 - Mariana",
                room="Box 03",
                initial_wait_min=12,
                current_waiting=2
            ),
            Queue(
                id="bistro",
                company_id="bistro",
                name="Mesa para 2 pessoas (Área Interna)",
                attendant_name="Hostess Bianca",
                room="Salão Principal",
                initial_wait_min=45,
                current_waiting=4
            )
        ]
        db.add_all(queues)

        # 3. Tickets for clinica-vida
        tickets = [
            Ticket(
                id="ticket-43",
                queue_id="clinica-vida",
                ticket_number="#43",
                customer_name="Maria Silva",
                service_name="Consulta Oftalmologia Geral",
                status="attending",
                position=0,
                is_user=False,
                is_priority=False,
                estimated_wait_text="Em atendimento",
                initial_wait_min=0,
                joined_at="14:05"
            ),
            Ticket(
                id="ticket-44",
                queue_id="clinica-vida",
                ticket_number="#44",
                customer_name="João Santos",
                service_name="Consulta Oftalmologia Geral",
                status="waiting",
                position=1,
                is_user=False,
                is_priority=False,
                estimated_wait_text="~10 min",
                initial_wait_min=10,
                joined_at="14:10"
            ),
            Ticket(
                id="ticket-45",
                queue_id="clinica-vida",
                ticket_number="#45",
                customer_name="Ana Costa",
                service_name="Exame de Fundo de Olho",
                status="waiting",
                position=2,
                is_user=False,
                is_priority=False,
                estimated_wait_text="~22 min",
                initial_wait_min=22,
                joined_at="14:15"
            ),
            Ticket(
                id="ticket-46",
                queue_id="clinica-vida",
                ticket_number="#46",
                customer_name="Pedro Lima",
                service_name="Retorno de Consulta",
                status="waiting",
                position=3,
                is_user=False,
                is_priority=False,
                estimated_wait_text="~34 min",
                initial_wait_min=34,
                joined_at="14:20"
            ),
            Ticket(
                id="ticket-47",
                queue_id="clinica-vida",
                ticket_number="#47",
                customer_name="Rafael",
                service_name="Consulta Oftalmologia Geral",
                status="waiting",
                position=4,
                is_user=True,
                is_priority=False,
                estimated_wait_text="~42 min",
                initial_wait_min=42,
                joined_at="14:25"
            ),
            Ticket(
                id="ticket-48",
                queue_id="clinica-vida",
                ticket_number="#48",
                customer_name="Mariana Alencar",
                service_name="Avaliação Cirúrgica",
                status="waiting",
                position=5,
                is_user=False,
                is_priority=True,
                estimated_wait_text="~55 min",
                initial_wait_min=55,
                joined_at="14:30"
            )
        ]
        db.add_all(tickets)

        # 4. Reception Waiting List Patients (Awaiting Secretary Insurance Authorization)
        reception_patients = [
            ReceptionPatient(
                id="rec-01",
                patient_name="Roberto Albuquerque",
                document="123.456.789-00",
                phone="(11) 98123-4567",
                insurance_name="Unimed",
                card_number="0048.2910.4431",
                procedure="Consulta Oftalmologia Geral",
                doctor_name="Dr. Carlos Mendes",
                room="Consultório 04",
                status="awaiting_auth",
                is_priority=False,
                notes="Carteirinha física apresentada no balcão"
            ),
            ReceptionPatient(
                id="rec-02",
                patient_name="Camila Fernandes",
                document="987.654.321-11",
                phone="(11) 97654-3210",
                insurance_name="Bradesco Saúde",
                card_number="8837.1902.4812",
                procedure="Exame de Fundo de Olho",
                doctor_name="Dr. Carlos Mendes",
                room="Consultório 04",
                status="verifying",
                is_priority=True,
                notes="Paciente preferencial (gestante) - token enviado por SMS"
            ),
            ReceptionPatient(
                id="rec-03",
                patient_name="Marcos Vinicius",
                document="456.789.123-22",
                phone="(11) 99112-8877",
                insurance_name="SulAmérica",
                card_number="5521.0948.3301",
                procedure="Retorno de Consulta",
                doctor_name="Dr. Carlos Mendes",
                room="Consultório 04",
                status="awaiting_auth",
                is_priority=False,
                notes="Chegou via check-in pelo aplicativo FilaFlow"
            ),
            ReceptionPatient(
                id="rec-04",
                patient_name="Juliana Menezes",
                document="332.112.445-99",
                phone="(11) 98877-6655",
                insurance_name="Amil Saúde",
                card_number="1192.4802.7734",
                procedure="Avaliação Pré-Operatória Catarata",
                doctor_name="Dr. Carlos Mendes",
                room="Consultório 04",
                status="authorized",
                auth_code="AUT-78219",
                ticket_number="#48",
                is_priority=False,
                authorized_at=datetime.utcnow()
            )
        ]
        db.add_all(reception_patients)

        db.commit()
        print("Banco de dados FilaFlow populado com sucesso!")
    except Exception as e:
        db.rollback()
        print(f"Erro ao popular banco de dados: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
