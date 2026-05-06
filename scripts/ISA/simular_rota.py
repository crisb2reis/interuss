import os, sys, time, math, requests
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.oir.models import IdentificationServiceArea

# --- Constantes ---
SPEED_M_S   = 5.0
INTERVAL_S  = 5.0
TELEMETRY_URL = "http://localhost:8001/uss/telemetry/"
MAX_RETRIES = 3


# --- Geometria (sem mudança) ---
def distance_and_bearing(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lam/2)**2
    dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    brng = (math.degrees(math.atan2(
        math.sin(d_lam)*math.cos(phi2),
        math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(d_lam)
    )) + 360) % 360
    return dist, brng


def destination_point(lat, lon, bearing, distance):
    R = 6371000
    phi1, lam1, brng = math.radians(lat), math.radians(lon), math.radians(bearing)
    phi2 = math.asin(
        math.sin(phi1)*math.cos(distance/R) +
        math.cos(phi1)*math.sin(distance/R)*math.cos(brng)
    )
    lam2 = lam1 + math.atan2(
        math.sin(brng)*math.sin(distance/R)*math.cos(phi1),
        math.cos(distance/R) - math.sin(phi1)*math.sin(phi2)
    )
    return math.degrees(phi2), math.degrees(lam2)


# --- Domínio ---
def fetch_isa(isa_id_str):
    """Busca o ISA por id ou dss_id."""
    try:
        return IdentificationServiceArea.objects.get(id=isa_id_str)
    except IdentificationServiceArea.DoesNotExist:
        pass
    try:
        return IdentificationServiceArea.objects.get(dss_id=isa_id_str)
    except IdentificationServiceArea.DoesNotExist:
        return None


def extract_route(isa):
    """Extrai pontos A/B e altitude do ISA. Retorna (point_a, point_b, altitude) ou None."""
    volume = isa.extents.get("volume", {})
    vertices = volume.get("outline_polygon", {}).get("vertices", [])
    if len(vertices) < 3:
        return None

    lats = [v["lat"] for v in vertices]
    lngs = [v["lng"] for v in vertices]
    point_a = (max(lats), min(lngs))  # Noroeste
    point_b = (min(lats), max(lngs))  # Sudeste

    alt_lower = volume.get("altitude_lower", {}).get("value", 100)
    alt_upper = volume.get("altitude_upper", {}).get("value", 200)
    altitude  = (alt_lower + alt_upper) / 2.0

    return point_a, point_b, altitude


# --- Telemetria ---
def send_telemetry(payload, retries=MAX_RETRIES):
    """Envia telemetria com retry simples."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(TELEMETRY_URL, json=payload, timeout=5)
            return resp.status_code
        except requests.RequestException as e:
            print(f"    [!] Tentativa {attempt}/{retries} falhou: {e}")
            time.sleep(1)
    return None


# --- Simulação ---
def simular_rota(isa_id_str):
    isa = fetch_isa(isa_id_str)
    if isa is None:
        print(f"[!] ISA não encontrado: {isa_id_str}")
        return

    result = extract_route(isa)
    if result is None:
        print("[!] Polígono inválido no ISA.")
        return

    point_a, point_b, altitude = result
    waypoints = [point_a, point_b]
    target_idx = 1  # começa indo para point_b
    current_lat, current_lng = point_a

    print(f"[*] ISA: {isa_id_str} | Rota: {point_a} <-> {point_b} | Alt: {altitude}m")

    while True:
        target_lat, target_lng = waypoints[target_idx]
        dist, bearing = distance_and_bearing(current_lat, current_lng, target_lat, target_lng)
        step = SPEED_M_S * INTERVAL_S

        if dist <= step:
            current_lat, current_lng = target_lat, target_lng
            target_idx = 1 - target_idx  # alterna 0 <-> 1
        else:
            current_lat, current_lng = destination_point(current_lat, current_lng, bearing, step)
            _, bearing = distance_and_bearing(current_lat, current_lng, *waypoints[target_idx])

        payload = {
            "isa_id":             str(isa.id),
            "timestamp":          datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "lat":                current_lat,
            "lng":                current_lng,
            "alt":                altitude,
            "pressure_altitude":  altitude,
            "operational_status": "Airborne",
            "speed":              SPEED_M_S,
            "track":              bearing,
            "accuracy_h":         "HA10m",
            "accuracy_v":         "VA10m",
            "speed_accuracy":     "SA3mps",
        }

        status = send_telemetry(payload)
        ts = datetime.now().strftime('%H:%M:%S')
        if status:
            print(f"[{ts}] {current_lat:.5f}, {current_lng:.5f} | Track: {bearing:.1f}° | HTTP {status}")
        else:
            print(f"[{ts}] Falha ao enviar telemetria após {MAX_RETRIES} tentativas.")

        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/ISA/simular_rota.py <ISA_ID_ou_OIR_ID>")
        sys.exit(1)
    print("Simulador iniciado (Ctrl+C para parar)...")
    try:
        simular_rota(sys.argv[1])
    except KeyboardInterrupt:
        print("\n[!] Simulação interrompida.")