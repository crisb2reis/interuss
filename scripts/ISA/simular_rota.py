import os, sys, time, math, requests
from datetime import datetime, timezone
from typing import Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import IdentificationServiceArea

# --- Constantes ---
SPEED_M_S     = 5.0
INTERVAL_S    = 5.0
TELEMETRY_URL = "http://localhost:8001/uss/telemetry/"
MAX_RETRIES   = 3


# --- Geometria ---
def distance_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """Retorna (distância em metros, rumo em graus 0-360)."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    brng = (math.degrees(math.atan2(
        math.sin(d_lam) * math.cos(phi2),
        math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lam),
    )) + 360) % 360
    return dist, brng


def destination_point(lat: float, lon: float, bearing: float, distance: float) -> Tuple[float, float]:
    """Calcula ponto de destino dado ponto de origem, rumo e distância (m)."""
    R = 6_371_000
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    brng = math.radians(bearing)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(distance / R)
        + math.cos(phi1) * math.sin(distance / R) * math.cos(brng)
    )
    lam2 = lam1 + math.atan2(
        math.sin(brng) * math.sin(distance / R) * math.cos(phi1),
        math.cos(distance / R) - math.sin(phi1) * math.sin(phi2),
    )
    # FIX: normaliza longitude para o intervalo [-180, 180]
    lon2 = (math.degrees(lam2) + 540) % 360 - 180
    return math.degrees(phi2), lon2


# --- Domínio ---
def fetch_isa(isa_id_str: str) -> Optional[IdentificationServiceArea]:
    """Busca o ISA por id ou dss_id."""
    for field in ("id", "dss_id"):
        try:
            return IdentificationServiceArea.objects.get(**{field: isa_id_str})
        except (IdentificationServiceArea.DoesNotExist, Exception):
            pass
    return None


def extract_route(isa: IdentificationServiceArea):
    """
    Extrai rota do ISA.
    Retorna:
      - ("linear",   point_a, point_b, altitude)
      - ("circular", center,  radius,  altitude)
      - None  →  geometria inválida
    """
    volume = isa.extents.get("volume", {})

    def _altitude(volume: dict, default_lower: float, default_upper: float) -> float:
        lower = volume.get("altitude_lower", {}).get("value", default_lower)
        upper = volume.get("altitude_upper", {}).get("value", default_upper)
        return (lower + upper) / 2.0

    # --- Circular ---
    circle = volume.get("outline_circle")
    if circle:
        center = circle.get("center")
        if not center or "lat" not in center or "lng" not in center:
            print("[!] outline_circle sem campo 'center' válido.")
            return None
        radius   = circle.get("radius", {}).get("value", 50)
        altitude = _altitude(volume, 600, 800)
        return "circular", center, radius, altitude

    # --- Linear (polígono) ---
    vertices = volume.get("outline_polygon", {}).get("vertices", [])
    if len(vertices) >= 2:
        # FIX: usa o primeiro e o último vértice explícitos em vez de inferir NW/SE,
        # preservando o sentido real da rota definida no polígono.
        point_a  = (vertices[0]["lat"],  vertices[0]["lng"])
        point_b  = (vertices[-1]["lat"], vertices[-1]["lng"])
        altitude = _altitude(volume, 0, 120)
        return "linear", point_a, point_b, altitude

    return None


# --- Telemetria ---
def send_telemetry(payload: dict, retries: int = MAX_RETRIES) -> Optional[int]:
    """Envia telemetria com retry simples. Retorna HTTP status ou None."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(TELEMETRY_URL, json=payload, timeout=5)
            # FIX: loga erros HTTP (4xx/5xx) sem tratá-los como sucesso
            if not resp.ok:
                print(f"    [!] HTTP {resp.status_code} — {resp.text[:120]}")
            return resp.status_code
        except requests.RequestException as e:
            print(f"    [!] Tentativa {attempt}/{retries} falhou: {e}")
            time.sleep(1)
    return None


# --- Helpers de payload ---
def _base_payload(isa: IdentificationServiceArea, lat: float, lng: float,
                  altitude: float, speed: float, track: float) -> dict:
    return {
        "isa_id":             str(isa.id),
        "timestamp":          datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lat":                lat,
        "lng":                lng,
        "alt":                altitude,
        "pressure_altitude":  altitude,
        "operational_status": "Airborne",
        "speed":              speed,
        "track":              round(track, 2),
        "accuracy_h":         "HA10m",
        "accuracy_v":         "VA10m",
        "speed_accuracy":     "SA3mps",
        "extrapolated":       False,
    }


# --- Simulação ---
def _loop_circular(isa: IdentificationServiceArea, center: dict,
                   radius: float, altitude: float) -> None:
    """
    FIX: acumula o ângulo a cada iteração em vez de derivá-lo do timestamp.
    Isso garante movimento contínuo mesmo após reinicializações e torna
    a velocidade angular coerente com SPEED_M_S e o raio configurado.
    """
    center_lat = center["lat"]
    center_lng = center["lng"]

    # velocidade angular (rad/s) derivada da velocidade linear e do raio
    if radius > 0:
        omega = SPEED_M_S / radius          # rad/s  →  v = ω·r
    else:
        omega = 0.05                        # fallback seguro
        print("[!] Raio zero/inválido; usando ω=0.05 rad/s como fallback.")

    print(
        f"[*] ISA: {isa.id} | Rota: CIRCULAR | "
        f"Centro: ({center_lat}, {center_lng}) | Raio: {radius} m | "
        f"Alt: {altitude} m | ω: {omega:.4f} rad/s"
    )

    angle = 0.0  # ângulo acumulado (radianos)

    while True:
        lat_offset = (radius * math.sin(angle)) / 111_320.0
        lng_offset = (radius * math.cos(angle)) / (
            111_320.0 * math.cos(math.radians(center_lat))
        )

        current_lat = center_lat + lat_offset
        current_lng = center_lng + lng_offset
        # track = direção tangencial ao círculo (perpendicular ao raio)
        track = (math.degrees(angle) + 90) % 360

        payload = _base_payload(isa, current_lat, current_lng, altitude, SPEED_M_S, track)
        status  = send_telemetry(payload)
        ts      = datetime.now().strftime("%H:%M:%S")
        if status:
            print(f"[{ts}] {current_lat:.6f}, {current_lng:.6f} | Track: {track:.1f}° | HTTP {status}")
        else:
            print(f"[{ts}] Falha ao enviar telemetria.")

        angle += omega * INTERVAL_S  # incremento angular para o próximo passo
        time.sleep(INTERVAL_S)


def _loop_linear(isa: IdentificationServiceArea, point_a: Tuple[float, float],
                 point_b: Tuple[float, float], altitude: float) -> None:
    waypoints  = [point_a, point_b]
    target_idx = 1
    current_lat, current_lng = point_a

    print(
        f"[*] ISA: {isa.id} | Rota: LINEAR | "
        f"{point_a} ↔ {point_b} | Alt: {altitude} m"
    )

    while True:
        target_lat, target_lng = waypoints[target_idx]
        dist, bearing = distance_and_bearing(current_lat, current_lng, target_lat, target_lng)
        step = SPEED_M_S * INTERVAL_S

        if dist <= step:
            current_lat, current_lng = target_lat, target_lng
            target_idx = 1 - target_idx
            _, bearing = distance_and_bearing(current_lat, current_lng, *waypoints[target_idx])
        else:
            current_lat, current_lng = destination_point(current_lat, current_lng, bearing, step)

        payload = _base_payload(isa, current_lat, current_lng, altitude, SPEED_M_S, bearing)
        status  = send_telemetry(payload)
        ts      = datetime.now().strftime("%H:%M:%S")
        if status:
            print(f"[{ts}] {current_lat:.6f}, {current_lng:.6f} | Track: {bearing:.1f}° | HTTP {status}")
        else:
            print(f"[{ts}] Falha ao enviar telemetria.")

        time.sleep(INTERVAL_S)


def simular_rota(isa_id_str: str) -> None:
    isa = fetch_isa(isa_id_str)
    if isa is None:
        print(f"[!] ISA não encontrado: {isa_id_str}")
        return

    route_data = extract_route(isa)
    if route_data is None:
        print("[!] Geometria inválida no ISA (necessário outline_circle ou outline_polygon).")
        return

    type_ = route_data[0]

    if type_ == "circular":
        _, center, radius, altitude = route_data
        _loop_circular(isa, center, radius, altitude)
    elif type_ == "linear":
        _, point_a, point_b, altitude = route_data
        _loop_linear(isa, point_a, point_b, altitude)
    else:
        print(f"[!] Tipo de rota desconhecido: {type_}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/ISA/simular_rota.py <ISA_ID_ou_OIR_ID>")
        sys.exit(1)
    print("Simulador iniciado (Ctrl+C para parar)...")
    try:
        simular_rota(sys.argv[1])
    except KeyboardInterrupt:
        print("\n[!] Simulação interrompida.")