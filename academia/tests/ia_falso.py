"""Servidor HTTP local que imita a API Messages da Anthropic, para testar o SDK oficial de ponta a ponta.

É uma SIMULAÇÃO: responde com textos fixos, guarda os pedidos recebidos e pode devolver os erros do provedor
(401, 404, 429, 529, conexão recusada) e recusa por segurança. Não substitui um teste com a API real.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROPOSTA = {"tipo": "treino_da_semana", "resumo": "Treino A mais curto", "treino": "A",
            "exercicios": ["supino_maquina", "puxada_polia", "leg_press"]}


class Falso:
    def __init__(self):
        self.pedidos: list[dict] = []
        self.modo = "texto"  # texto | ferramenta | recusa | 401 | 404 | 429 | 529 | 400
        self.texto = "### Treino de hoje\nFaça o **treino A** com calma."
        self.proposta = PROPOSTA
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def fechar(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _handler(self):
        falso = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, status, corpo):
                dados = json.dumps(corpo).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("x-should-retry", "false")  # o SDK não repete: os testes ficam rápidos
                self.send_header("content-length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_POST(self):
                corpo = json.loads(self.rfile.read(int(self.headers["content-length"])))
                falso.pedidos.append({"corpo": corpo, "headers": dict(self.headers)})
                erros = {"401": ("authentication_error", "invalid x-api-key"), "404": ("not_found_error", "model"),
                         "429": ("rate_limit_error", "rate limited"), "529": ("overloaded_error", "Overloaded"),
                         "400": ("invalid_request_error", "bad")}
                if falso.modo in erros:
                    tipo, msg = erros[falso.modo]
                    return self._json(int(falso.modo), {"type": "error", "error": {"type": tipo, "message": msg}})
                texto = falso.texto if falso.modo != "recusa" else ""
                stop = {"recusa": "refusal", "ferramenta": "tool_use"}.get(falso.modo, "end_turn")
                if not corpo.get("stream"):
                    return self._json(200, {"id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"],
                                            "content": [{"type": "text", "text": "- resumo de teste"}],
                                            "stop_reason": "end_turn", "stop_sequence": None,
                                            "usage": {"input_tokens": 50, "output_tokens": 5}})
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()

                def ev(nome, dados):
                    self.wfile.write(f"event: {nome}\ndata: {json.dumps(dados)}\n\n".encode())

                ev("message_start", {"type": "message_start", "message": {
                    "id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"], "content": [],
                    "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1200, "output_tokens": 1}}})
                i = 0
                if texto:
                    ev("content_block_start", {"type": "content_block_start", "index": 0,
                                                "content_block": {"type": "text", "text": ""}})
                    for k in range(0, len(texto), 12):
                        ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                    "delta": {"type": "text_delta", "text": texto[k:k + 12]}})
                    ev("content_block_stop", {"type": "content_block_stop", "index": 0})
                    i = 1
                if falso.modo == "ferramenta":
                    ev("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                        "type": "tool_use", "id": "toolu_1", "name": "propor_alteracao", "input": {}}})
                    ev("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                        "type": "input_json_delta", "partial_json": json.dumps(falso.proposta, ensure_ascii=False)}})
                    ev("content_block_stop", {"type": "content_block_stop", "index": i})
                ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                     "usage": {"output_tokens": 42}})
                ev("message_stop", {"type": "message_stop"})

        return H
