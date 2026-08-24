from fastapi import FastAPI, Response, status
import uvicorn
from threading import Thread

class KioskApiServer:
    def __init__(self, host="127.0.0.1", port=8081):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.thread = None
        self.callbacks = {}
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/overlay")
        async def check_overlay():
            if "is_overlay_active" in self.callbacks:
                active = self.callbacks["is_overlay_active"]()
                return {"active": active}
            return {"active": False}

        @self.app.post("/overlay")
        async def open_overlay(url: str):
            if "open_overlay" in self.callbacks:
                self.callbacks["open_overlay"](url)
                return {"status": "ok", "message": "Åpner overlay"}
            return Response(status_code=404)

        @self.app.delete("/overlay")
        async def close_overlay():
            if "close_overlay" in self.callbacks:
                self.callbacks["close_overlay"]()
                return {"status": "ok", "message": "Lukker overlay"}
            return Response(status_code=404)

    def register_callback(self, name, func):
        self.callbacks[name] = func

    def start(self):
        def run():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")
        
        self.thread = Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        pass