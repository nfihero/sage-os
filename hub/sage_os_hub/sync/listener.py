"""The sync listener and its client (P1, D45): the only part of Sage OS another computer can reach.

It runs only while this device has a paired device or is hosting a pairing, on its own port (8789 by default),
separate from the hub's own localhost-only port, and it answers four requests: hello, pair, ping and unpair. Its TLS
certificate is made fresh each start; the private key is in memory only (written to a temporary file just long
enough for the TLS library to read it). Devices find each other with Bonjour/mDNS (zeroconf).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, HTTPException, Request

from .devicekey import DeviceKey, _unb64
from .peers import PairingError, b64, hello_message, proof, tls_fingerprint

log = logging.getLogger("sage_os.sync")
SERVICE = "_sage-os._tcp.local."
TIMEOUT = httpx.Timeout(10, connect=5)
MAX_BODY = 64 * 1024                                   # P1's requests are tiny; P2 will raise this for its own route


# -- the certificate -----------------------------------------------------------------------------------------------
def make_cert() -> tuple[bytes, bytes]:
    """A fresh self-signed TLS certificate (P-256). -> (key PEM, cert PEM). Trust comes from `hello`, not from it."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sage-os")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=30)).sign(key, hashes.SHA256()))
    return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
            cert.public_bytes(serialization.Encoding.PEM))


def addresses() -> list[str]:
    """This computer's addresses on its local networks (for the person, and for mDNS)."""
    out = set()
    try:
        import ifaddr
        for a in ifaddr.get_adapters():
            for ip in a.ips:
                if isinstance(ip.ip, str) and not ip.ip.startswith(("127.", "169.254.")):
                    out.add(ip.ip)
    except Exception:                                 # noqa: BLE001 -- best effort
        pass
    if not out:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                out.add(s.getsockname()[0])
        except OSError:
            pass
    return sorted(out, key=lambda ip: (not ip.startswith("192.168."), not ip.startswith("10."), ip))   # home networks first


# -- the app other devices talk to ---------------------------------------------------------------------------------
def sync_app(svc: "SyncService") -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    peers = svc.peers

    @app.get("/sync/hello")
    def hello():
        """Who this is, and its signature over this run's certificate (so the caller can tell it's really us)."""
        me = peers.me
        return {"id": peers.device_id, "name": peers.name, "pubkey": me.public_b64,
                "sig": b64(me.sign(hello_message(peers.device_id, svc.tls_fpr))), "pairing": peers.pairing() is not None}

    @app.post("/sync/pair")
    async def pair(request: Request):
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "too big")
        try:
            req = json.loads(raw or b"{}")
            ans = peers.accept(req, svc.tls_fpr)
        except PairingError as exc:
            raise HTTPException(403, str(exc))
        except ValueError:
            raise HTTPException(400, "bad request")
        svc.changed()
        return ans

    async def signed(request: Request) -> dict:
        body = await request.body()
        if len(body) > MAX_BODY:
            raise HTTPException(413, "too big")
        try:
            peer = peers.verify(request.method, request.url.path, request.headers, body, svc.tls_fpr)
        except PermissionError as exc:
            raise HTTPException(401, str(exc))
        peers.seen(peer["id"])
        return peer

    @app.post("/sync/ping")
    async def ping(request: Request):
        peer = await signed(request)
        return {"id": peers.device_id, "name": peers.name, "you": peer["id"], "time": time.time()}

    @app.post("/sync/unpair")
    async def unpair(request: Request):
        peer = await signed(request)
        peers.remove(peer["id"])
        svc.changed()
        return {"removed": peer["id"]}

    return app


# -- talking to another device -------------------------------------------------------------------------------------
class Peer:
    """A TLS connection to another device whose `hello` has been checked: its certificate on this very connection is
    signed by the identity key we expect (or, while pairing, by the key it claims, checked later with the code)."""

    def __init__(self, address: str, expect_key: str | None = None):
        self.address = address if ":" in address.split("]")[-1] else f"{address}:{SyncService.PORT}"
        self.client = httpx.Client(base_url=f"https://{self.address}", verify=False, timeout=TIMEOUT,
                                   limits=httpx.Limits(max_connections=1, max_keepalive_connections=1))
        self.tls_fpr: str | None = None
        r = self.client.get("/sync/hello")
        r.raise_for_status()
        fpr = self._fpr(r)
        h = r.json()
        key = expect_key or h.get("pubkey")
        if expect_key and h.get("pubkey") != expect_key:
            raise PermissionError("that device has a different key than the one paired with")
        if not key or not DeviceKey.verify(key, _unb64(h.get("sig", "")), hello_message(h.get("id", ""), fpr)):
            raise PermissionError("that device couldn't prove who it is")
        self.tls_fpr, self.hello = fpr, h

    @staticmethod
    def _fpr(r: httpx.Response) -> str:
        stream = r.extensions.get("network_stream")
        ssl_obj = stream.get_extra_info("ssl_object") if stream is not None else None
        der = ssl_obj.getpeercert(True) if ssl_obj is not None else None
        if not der:
            raise PermissionError("no TLS certificate on that connection")
        return tls_fingerprint(der)

    def post(self, path: str, body: dict, peers=None) -> dict:
        raw = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if peers is not None:
            headers |= peers.sign("POST", path, raw, self.tls_fpr)
        r = self.client.post(path, content=raw, headers=headers)
        if self._fpr(r) != self.tls_fpr:              # still the same, checked connection
            raise PermissionError("the connection changed")
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except ValueError:
                detail = r.text[:200]
            raise PairingError(detail or f"HTTP {r.status_code}")
        return r.json()

    def close(self):
        self.client.close()


def connect(address: str, expect_key: str | None = None) -> Peer:
    """`address` may list several, comma-separated (what mDNS found): the first that answers and proves itself wins."""
    last: Exception | None = None
    for a in [x.strip() for x in address.split(",") if x.strip()]:
        try:
            return Peer(a, expect_key)
        except (httpx.HTTPError, OSError) as exc:
            last = exc
    if isinstance(last, Exception):
        raise last
    raise OSError("no address")


# -- the service ---------------------------------------------------------------------------------------------------
class SyncService:
    """Starts the listener when it's needed (a paired device, or a pairing in progress) and stops it when it isn't;
    advertises this device on the local network while it runs; finds others."""
    PORT = 8789

    def __init__(self, hub, port: int | None = None, host: str = "0.0.0.0", mdns: bool = True):
        self.hub, self.peers = hub, hub.peers
        self.port, self.host, self.mdns = port if port is not None else self.PORT, host, mdns
        self.server = None
        self.task: asyncio.Task | None = None
        self.tls_fpr: str | None = None
        self.bound: int | None = None
        self._zc = None
        self._browser = None
        self.nearby: dict[str, dict] = {}
        self.error: str | None = None

    def needed(self) -> bool:
        return self.peers.me is not None and (bool(self.peers.all()) or self.peers.pairing() is not None)

    def changed(self) -> None:
        """Something about pairing changed: start or stop the listener to match, and tell the screen."""
        loop = self.hub.loop
        if loop is not None:
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.apply()))
        self.hub.publish({"t": "devices"})

    async def apply(self) -> None:
        if self.needed() and self.task is None:
            await self.start()
        elif not self.needed() and self.task is not None:
            await self.stop()

    async def start(self) -> None:
        import uvicorn
        key_pem, cert_pem = make_cert()
        self.tls_fpr = tls_fingerprint(x509.load_pem_x509_certificate(cert_pem).public_bytes(serialization.Encoding.DER))
        tmp = Path(tempfile.mkdtemp(prefix="sage-sync-"))
        kf, cf = tmp / "k.pem", tmp / "c.pem"
        fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key_pem)
        cf.write_bytes(cert_pem)
        cfg = uvicorn.Config(sync_app(self), host=self.host, port=self.port, ssl_keyfile=str(kf), ssl_certfile=str(cf),
                             log_level="warning", log_config=None, lifespan="off")
        try:
            cfg.load()                                # reads the key into memory; then the files go
        finally:
            kf.unlink(missing_ok=True)
            cf.unlink(missing_ok=True)
            tmp.rmdir()
        self.server = uvicorn.Server(cfg)
        self.server.install_signal_handlers = lambda: None
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(100):
            if self.server.started or self.task.done():
                break
            await asyncio.sleep(0.05)
        if self.task.done():
            exc = self.task.exception()
            self.error = f"couldn't open the sync port {self.port}: {exc}" if exc else f"couldn't open the sync port {self.port}"
            log.warning(self.error)
            self.task, self.server = None, None
            return
        self.error = None
        self.bound = self.server.servers[0].sockets[0].getsockname()[1] if self.server.servers else self.port
        log.info("sync listener on port %s", self.bound)
        if self.mdns:
            await asyncio.to_thread(self._advertise)

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, 5)
            except (asyncio.TimeoutError, Exception):      # noqa: BLE001
                pass
        self.task, self.server, self.bound = None, None, None
        await asyncio.to_thread(self._unadvertise)

    # -- Bonjour / mDNS ----------------------------------------------------------------------------------------
    def _zeroconf(self):
        if self._zc is None:
            from zeroconf import Zeroconf
            self._zc = Zeroconf()
        return self._zc

    def _info(self):
        from zeroconf import ServiceInfo
        return ServiceInfo(SERVICE, f"{self.peers.device_id}.{SERVICE}", port=self.bound,
                           addresses=[socket.inet_aton(a) for a in addresses() if "." in a],
                           properties={"id": self.peers.device_id, "name": self.peers.name})

    def _advertise(self) -> None:
        try:
            self._zeroconf().register_service(self._info(), allow_name_change=True)
        except Exception as exc:                      # noqa: BLE001 -- pairing by address still works
            log.warning("couldn't announce this device on the network: %s", exc)

    def _unadvertise(self) -> None:
        if self._zc is not None:
            try:
                self._zc.unregister_all_services()
            except Exception:                         # noqa: BLE001
                pass

    def browse(self) -> list[dict]:
        """Sage OS devices announcing themselves on this network right now (other than this one)."""
        if not self.mdns:
            return list(self.nearby.values())
        if self._browser is None:
            from zeroconf import ServiceBrowser, ServiceStateChange
            svc = self

            def on_change(zeroconf, service_type, name, state_change):
                if state_change is ServiceStateChange.Removed:
                    svc.nearby.pop(name, None)
                    return
                info = zeroconf.get_service_info(service_type, name, 2000)
                if not info:
                    return
                props = {k.decode(): (v or b"").decode() for k, v in (info.properties or {}).items()}
                if props.get("id") == svc.peers.device_id:
                    return
                ips = sorted(info.parsed_addresses(), key=lambda ip: (not ip.startswith("192.168."), ":" in ip))
                if ips:                               # a computer can announce virtual adapters too: keep every address
                    svc.nearby[name] = {"id": props.get("id"), "name": props.get("name") or "Sage OS",
                                        "address": ",".join(f"{ip}:{info.port}" for ip in ips), "seen": time.time()}
            try:
                self._browser = ServiceBrowser(self._zeroconf(), SERVICE, handlers=[on_change])
            except Exception as exc:                  # noqa: BLE001
                log.warning("couldn't look for devices on the network: %s", exc)
        return sorted(self.nearby.values(), key=lambda d: d["name"])

    def close(self) -> None:
        if self._zc is not None:
            try:
                self._zc.close()
            except Exception:                         # noqa: BLE001
                pass
            self._zc = None

    # -- pairing from this side, and checks ---------------------------------------------------------------------
    def join(self, address: str, code: str) -> dict:
        """Pair with a device that's showing a code. -> the paired device. Runs in a worker thread."""
        me = self.peers
        if me.me is None:
            raise PairingError("this computer has no keychain, so it has no pairing key")
        try:
            p = connect(address)
        except (httpx.HTTPError, OSError) as exc:
            raise PairingError(f"couldn't reach that device: is Sage OS open there, showing a code? ({type(exc).__name__})")
        except PermissionError as exc:
            raise PairingError(str(exc))
        try:
            host = p.hello
            if host.get("id") == me.device_id:
                raise PairingError("that's this device")
            ans = p.post("/sync/pair", {"id": me.device_id, "name": me.name, "pubkey": me.me.public_b64,
                                        "proof": proof(code, "join", me.me.public_b64, host["pubkey"], p.tls_fpr)})
            want = proof(code, "host", host["pubkey"], me.me.public_b64)
            import hmac as _hmac
            if ans.get("pubkey") != host["pubkey"] or not _hmac.compare_digest(str(ans.get("proof", "")), want):
                raise PairingError("the other device's answer didn't match the code; nothing was paired")
            me.add(host["id"], host.get("name") or "Sage OS", host["pubkey"], p.address)
            me.seen(host["id"], p.address)
            peer = me.get(host["id"])
        finally:
            p.close()
        self.changed()
        return peer

    def check(self, device_id: str) -> dict:
        """Reach a paired device and prove both sides. -> its answer. Runs in a worker thread."""
        peer = self.peers.get(device_id)
        if peer is None:
            raise PairingError("not a paired device")
        found = next((n for n in self.nearby.values() if n.get("id") == device_id), None)
        address = (found or {}).get("address") or peer.get("address")
        if not address:
            raise PairingError(f"{peer['name']} hasn't been seen on this network yet")
        try:
            p = connect(address, expect_key=peer["pubkey"])
        except (httpx.HTTPError, OSError):
            raise PairingError(f"couldn't reach {peer['name']}: is it on, with Sage OS open, on this network?")
        except PermissionError as exc:
            raise PairingError(str(exc))
        try:
            ans = p.post("/sync/ping", {}, self.peers)
        finally:
            p.close()
        self.peers.seen(device_id, p.address)
        return ans

    def tell_removed(self, device_id: str) -> None:
        """Best effort: let the other device know it was removed, so it stops trying."""
        peer = next((x for x in self.peers.all(include_removed=True) if x["id"] == device_id), None)
        if not peer or not peer.get("address"):
            return
        try:
            p = connect(peer["address"], expect_key=peer["pubkey"])
            try:
                p.post("/sync/unpair", {}, self.peers)
            finally:
                p.close()
        except Exception:                             # noqa: BLE001 -- it'll be refused anyway
            pass
