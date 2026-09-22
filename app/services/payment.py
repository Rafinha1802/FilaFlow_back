from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import base64
import uuid
import logging

from app.models.order import SubscriptionOrder
from app.routers.websocket import ws_manager

logger = logging.getLogger("filaflow.payment")

def calculate_crc16(payload: str) -> str:
    """Calcula o checksum CRC16-CCITT (0x1021) no padrão oficial do Banco Central do Brasil para o Pix."""
    crc = 0xFFFF
    for char in payload:
        crc ^= (ord(char) << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def generate_pix_copia_e_cola(
    key: str,
    merchant_name: str,
    merchant_city: str,
    amount: float,
    txid: str
) -> str:
    """Gera string no padrão EMV BR Code (Pix Copia e Cola) válido."""
    # 00: Payload Format Indicator
    f00 = "000201"
    
    # 26: Merchant Account Information
    # 00: GUI (br.gov.bcb.pix)
    # 01: Chave Pix
    gui = "0014br.gov.bcb.pix"
    key_field = f"01{len(key):02d}{key}"
    mai_content = f"{gui}{key_field}"
    f26 = f"26{len(mai_content):02d}{mai_content}"
    
    # 52: Merchant Category Code
    f52 = "52040000"
    # 53: Transaction Currency (986 = BRL)
    f53 = "5303986"
    # 54: Transaction Amount
    amount_str = f"{amount:.2f}"
    f54 = f"54{len(amount_str):02d}{amount_str}"
    # 58: Country Code (BR)
    f58 = "5802BR"
    # 59: Merchant Name (max 25 chars)
    name_clean = merchant_name[:25]
    f59 = f"59{len(name_clean):02d}{name_clean}"
    # 60: Merchant City (max 15 chars)
    city_clean = merchant_city[:15]
    f60 = f"60{len(city_clean):02d}{city_clean}"
    # 62: Additional Data Field (TxID)
    txid_clean = txid[:25]
    f62_content = f"05{len(txid_clean):02d}{txid_clean}"
    f62 = f"62{len(f62_content):02d}{f62_content}"
    
    # Montagem sem o CRC
    partial = f"{f00}{f26}{f52}{f53}{f54}{f58}{f59}{f60}{f62}6304"
    crc = calculate_crc16(partial)
    return f"{partial}{crc}"

class PaymentGatewayService:
    """Serviço de Gateway de Pagamento (Mercado Pago / Pix / Asaas)."""

    @staticmethod
    def process_new_order(order: SubscriptionOrder) -> Dict[str, Any]:
        """Processa a criação de um pedido, gerando credenciais Pix ou de cartão."""
        txid = f"FF{order.id.replace('ord-', '')[:8].upper()}"
        pix_key = "pix@filaflow.com.br"
        
        pix_code = generate_pix_copia_e_cola(
            key=pix_key,
            merchant_name="FilaFlow Tecnologia",
            merchant_city="SAO PAULO",
            amount=order.amount or 189.0,
            txid=txid
        )

        # SVG placeholder representativo codificado em base64
        svg_qr = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#ffffff"/><rect x="10" y="10" width="25" height="25" fill="#000000"/><rect x="65" y="10" width="25" height="25" fill="#000000"/><rect x="10" y="65" width="25" height="25" fill="#000000"/><rect x="40" y="40" width="20" height="20" fill="#10B981"/><text x="50" y="55" font-size="8" fill="#ffffff" text-anchor="middle">PIX</text></svg>'
        qr_base64 = f"data:image/svg+xml;base64,{base64.b64encode(svg_qr.encode('utf-8')).decode('utf-8')}"

        order.status = "pending"
        order.pix_code = pix_code
        order.pix_qr_code_base64 = qr_base64
        order.gateway = "mercadopago"

        return {
            "order_id": order.id,
            "status": "pending",
            "amount": order.amount,
            "pix_code": pix_code,
            "pix_qr_code_base64": qr_base64,
            "expires_in_minutes": 30
        }

    @staticmethod
    async def confirm_payment(
        order_id: str,
        db: Session,
        gateway_payment_id: Optional[str] = None
    ) -> SubscriptionOrder:
        """Confirma o pagamento de um pedido pendente (via webhook ou simulação bancária)."""
        order = db.query(SubscriptionOrder).filter(SubscriptionOrder.id == order_id).first()
        if not order:
            raise ValueError(f"Pedido '{order_id}' não encontrado")

        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)

        # Emitir notificação WebSocket global ou da empresa
        await ws_manager.broadcast({
            "type": "PAYMENT_CONFIRMED",
            "orderId": order.id,
            "companyName": order.company_name,
            "planName": order.plan_name,
            "status": "paid",
            "paidAt": order.paid_at.isoformat()
        })

        return order
