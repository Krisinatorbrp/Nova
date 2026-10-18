"""Announces Nova on your Wi-Fi (Bonjour) so the iPhone app finds your PC automatically."""
import socket

from server import phone_urls


def advertise(cfg):
    """Returns a handle to keep alive, or None if zeroconf isn't available."""
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except Exception:
        return None
    port = cfg["port"]
    urls = phone_urls(port)
    ips = [u["url"].split("//")[1].rsplit(":", 1)[0] for u in urls if "Wi-Fi" in u["kind"]]
    if not ips:
        return None
    host = socket.gethostname().split(".")[0][:40] or "PC"
    try:
        zc = Zeroconf()
        info = ServiceInfo(
            "_nova._tcp.local.",
            f"Nova on {host}._nova._tcp.local.",
            addresses=[socket.inet_aton(ip) for ip in ips],
            port=port,
            properties={"name": cfg.get("assistant_name", "Nova"), "host": host,
                        "ips": ",".join(ips), "port": str(port)},
            server=f"{host.lower()}-nova.local.",
        )
        zc.register_service(info)
        return zc
    except Exception as e:
        print(f"Wi-Fi discovery not available: {e}")
        return None
