from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import List, Dict, Set, Any, Optional
from collections import defaultdict
import json
import logging

from app.core.security import decode_access_token

router = APIRouter(tags=["WebSockets"])
logger = logging.getLogger("filaflow.websocket")

class ConnectionManager:
    def __init__(self):
        # Mapeamento sala -> conjunto de conexões ativas
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
        # Mapeamento reverso conexão -> conjunto de salas das quais participa
        self.socket_rooms: Dict[WebSocket, Set[str]] = defaultdict(set)
        # Conexões ativas sem sala específica atribuída
        self.unassigned: Set[WebSocket] = set()

    async def connect(
        self,
        websocket: WebSocket,
        company_id: Optional[str] = None,
        queue_id: Optional[str] = None
    ):
        """Aceita a conexão WebSocket e a registra nas salas informadas."""
        await websocket.accept()
        registered_in_room = False

        if company_id:
            self.join_room(websocket, f"company:{company_id}")
            registered_in_room = True

        if queue_id:
            self.join_room(websocket, f"queue:{queue_id}")
            registered_in_room = True

        if not registered_in_room:
            self.unassigned.add(websocket)

        logger.info(
            f"WebSocket conectado. Company: {company_id}, Queue: {queue_id}. "
            f"Total de salas ativas: {len(self.rooms)}"
        )

    def join_room(self, websocket: WebSocket, room: str):
        """Adiciona uma conexão a uma sala específica."""
        self.rooms[room].add(websocket)
        self.socket_rooms[websocket].add(room)
        if websocket in self.unassigned:
            self.unassigned.remove(websocket)
        logger.debug(f"Socket adicionado à sala '{room}'. Total na sala: {len(self.rooms[room])}")

    def leave_room(self, websocket: WebSocket, room: str):
        """Remove uma conexão de uma sala específica."""
        if room in self.rooms and websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)
            if not self.rooms[room]:
                del self.rooms[room]
        if websocket in self.socket_rooms and room in self.socket_rooms[websocket]:
            self.socket_rooms[websocket].remove(room)

    def disconnect(self, websocket: WebSocket):
        """Desconecta e remove a conexão de todas as salas registradas."""
        rooms = list(self.socket_rooms.get(websocket, set()))
        for room in rooms:
            if room in self.rooms and websocket in self.rooms[room]:
                self.rooms[room].remove(websocket)
                if not self.rooms[room]:
                    del self.rooms[room]
        
        if websocket in self.socket_rooms:
            del self.socket_rooms[websocket]

        if websocket in self.unassigned:
            self.unassigned.remove(websocket)

        logger.info("WebSocket desconectado e removido de todas as salas.")

    async def broadcast(
        self,
        message: Dict[str, Any],
        company_id: Optional[str] = None,
        queue_id: Optional[str] = None
    ):
        """Transmite uma mensagem apenas para as conexões da empresa e/ou fila de destino.
        Impede vazamento de dados entre empresas."""
        # Detectar identificadores a partir do payload se não passados explicitamente
        cid = company_id or message.get("company_id") or message.get("companyId")
        qid = queue_id or message.get("queue_id") or message.get("queueId")

        target_sockets: Set[WebSocket] = set()

        if cid:
            target_sockets.update(self.rooms.get(f"company:{cid}", set()))

        if qid:
            target_sockets.update(self.rooms.get(f"queue:{qid}", set()))

        # Se nenhum filtro for aplicável (broadcast global intencional), transmite para todos
        if not cid and not qid:
            for s_set in self.rooms.values():
                target_sockets.update(s_set)
            target_sockets.update(self.unassigned)

        if not target_sockets:
            logger.debug(f"Nenhum cliente conectado para a sala company:{cid} ou queue:{qid}.")
            return

        message_str = json.dumps(message)
        dead_sockets = []

        for socket in list(target_sockets):
            try:
                await socket.send_text(message_str)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem WebSocket: {e}")
                dead_sockets.append(socket)

        for socket in dead_sockets:
            self.disconnect(socket)

ws_manager = ConnectionManager()

async def handle_ws_session(
    websocket: WebSocket,
    company_id: Optional[str] = None,
    queue_id: Optional[str] = None,
    token: Optional[str] = None
):
    """Trata o ciclo de vida da conexão WebSocket e comandos de assinatura in-band."""
    # Se um token foi fornecido na query string, extrai a empresa autenticada
    if token and not company_id:
        token_payload = decode_access_token(token)
        if token_payload and token_payload.get("sub"):
            company_id = token_payload.get("sub")

    await ws_manager.connect(websocket, company_id=company_id, queue_id=queue_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                
                # Ping-Pong para manter conexão ativa
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
                # Assinatura dinâmica de salas in-band
                elif msg_type in ("subscribe", "join_room", "SUBSCRIBE"):
                    sub_company = msg.get("company_id") or msg.get("companyId")
                    sub_queue = msg.get("queue_id") or msg.get("queueId")
                    sub_token = msg.get("token")

                    if sub_token and not sub_company:
                        tp = decode_access_token(sub_token)
                        if tp and tp.get("sub"):
                            sub_company = tp.get("sub")

                    if sub_company:
                        ws_manager.join_room(websocket, f"company:{sub_company}")
                    if sub_queue:
                        ws_manager.join_room(websocket, f"queue:{sub_queue}")

                    await websocket.send_text(json.dumps({
                        "type": "SUBSCRIBED",
                        "companyId": sub_company,
                        "queueId": sub_queue
                    }))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erro na conexão WebSocket: {e}")
        ws_manager.disconnect(websocket)

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    company_id: Optional[str] = Query(None),
    queue_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """Endpoint WebSocket principal com filtros de sala por query param ou token."""
    await handle_ws_session(websocket, company_id=company_id, queue_id=queue_id, token=token)

@router.websocket("/ws/{company_id}")
async def websocket_company_endpoint(
    websocket: WebSocket,
    company_id: str,
    queue_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """Endpoint WebSocket direto por ID da empresa."""
    await handle_ws_session(websocket, company_id=company_id, queue_id=queue_id, token=token)
