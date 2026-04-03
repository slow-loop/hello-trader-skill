import httpx
from skill_crypto_trader.journal.helpers import get_freqtrade_userdata

def _get_api_config():
    config_path = get_freqtrade_userdata() / "config_active.json"
    if not config_path.exists():
        return {"ip": "127.0.0.1", "port": 8080, "username": "", "password": ""}
    
    import json
    with open(config_path) as f:
        config = json.load(f)
    
    api_cfg = config.get("api_server", {})
    return {
        "ip": api_cfg.get("listen_ip_address", "127.0.0.1"),
        "port": api_cfg.get("listen_port", 8080),
        "username": api_cfg.get("username", ""),
        "password": api_cfg.get("password", "")
    }

def get_client() -> httpx.Client:
    cfg = _get_api_config()
    base_url = f"http://{cfg['ip']}:{cfg['port']}"
    
    auth = None
    if cfg["username"] and cfg["password"]:
        auth = (cfg["username"], cfg["password"])
    
    client = httpx.Client(base_url=base_url)
    if auth:
        # Avoid using the client instance itself for the token request to prevent state pollution
        resp = httpx.post(f"{base_url}/api/v1/token", auth=auth)
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            client.headers.update({"Authorization": f"Bearer {token}"})
        else:
            # Fallback to basic auth or at least don't fail silently
            client.auth = auth
    
    return client

def force_enter(pair: str, side: str, price: float | None = None, ordertype: str = "limit"):
    with get_client() as client:
        payload = {"pair": pair, "side": side, "ordertype": ordertype}
        if price is not None:
            payload["price"] = price
        resp = client.post("/api/v1/forceenter", json=payload)
        resp.raise_for_status()
        return resp.json()

def force_exit(trade_id: str):
    with get_client() as client:
        payload = {"tradeid": trade_id}
        resp = client.post("/api/v1/forceexit", json=payload)
        resp.raise_for_status()
        return resp.json()

def query_status():
    with get_client() as client:
        resp = client.get("/api/v1/status")
        resp.raise_for_status()
        return resp.json()

def query_trades():
    with get_client() as client:
        resp = client.get("/api/v1/trades")
        resp.raise_for_status()
        return resp.json()
