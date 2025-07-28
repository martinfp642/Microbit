# -------- Pulse Meter v9  (valor + corazón en loop) --------
from microbit import *
import music

# ------------------ Parámetros ------------------
PIN_SENSOR      = pin0
FS              = 100               # 100 Hz
DT_MS           = 1000 // FS
WINDOW_MS       = 20000             # 20 s
COUNTDOWN_SEC   = 3                 # cuenta atrás 3 s

K_THRESHOLD     = 1.0
REFRACT_MS      = 600
IBI_MIN_MS      = 400
EMA_ALPHA       = 0.95
IBI_BUF_SIZE    = 5
INVERTIDO       = True              # sensores LED verde → valles

# ------------------ Utilidades ------------------
def beep(pin_out=None):
    music.pitch(880, 60, pin=pin_out, wait=False)   # v2: altavoz interno

ema = var = thr = 0
def update_stats(x):
    global ema, var, thr
    ema = EMA_ALPHA*ema + (1-EMA_ALPHA)*x
    var = EMA_ALPHA*var + (1-EMA_ALPHA)*(x-ema)**2
    thr = ema - K_THRESHOLD*(var**0.5) if INVERTIDO else ema + K_THRESHOLD*(var**0.5)

# Mediana sencilla
def median(lst):
    s = sorted(lst); n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

# Secuencia LED progreso (20 primeros LEDs, fila a fila)
PROGRESO = [(x, y) for y in range(5) for x in range(5)][:20]

# ------------------ Estados ------------------
IDLE, COUNTDOWN, MEASURING, SHOW_LOOP = range(4)
state = IDLE

# ------------------ Variables ------------------
last_beat   = 0
ibis        = []
beats_total = 0
t_start     = 0
last_sec    = -1
valor_text  = ""

def reset_measurement():
    global last_beat, ibis, beats_total, t_start, last_sec
    last_beat = 0
    ibis.clear()
    beats_total = 0
    t_start = running_time()
    last_sec = -1
    display.clear()

def cuenta_regresiva():
    for n in reversed(range(1, COUNTDOWN_SEC+1)):
        display.show(str(n)); beep()
        for _ in range(int(1000/DT_MS)):
            sleep(DT_MS)
            if button_b.was_pressed():
                return False
    display.show(Image.HAPPY); beep(); sleep(300); display.clear()
    return True

# ------------------ Bucle principal ------------------
display.show(Image.SQUARE_SMALL)      # modo espera

while True:

    # ---- ESPERA ----
    if state == IDLE and button_a.was_pressed():
        state = COUNTDOWN

    # ---- CUENTA REGRESIVA ----
    elif state == COUNTDOWN:
        if cuenta_regresiva():
            reset_measurement()
            state = MEASURING
        else:
            continue

    # ---- MEDICIÓN 20 s ----
    elif state == MEASURING:
        if button_b.was_pressed():          # cancelar y reiniciar
            state = COUNTDOWN
            continue

        raw = PIN_SENSOR.read_analog()
        update_stats(raw)
        now = running_time()

        # Barra de progreso (LED por segundo)
        sec = (now - t_start) // 1000
        if sec != last_sec and sec < 20:
            x, y = PROGRESO[sec]
            display.set_pixel(x, y, 9)
            last_sec = sec

        # Detección de latido
        cond = (raw < thr) if INVERTIDO else (raw > thr)
        if cond and (now - last_beat) > REFRACT_MS:
            if last_beat:
                ibi = now - last_beat
                if ibi >= IBI_MIN_MS:
                    ibis.append(ibi)
                    if len(ibis) > IBI_BUF_SIZE:
                        ibis.pop(0)
                    beats_total += 1
                    beep()
            last_beat = now

        # Fin de ventana
        if now - t_start >= WINDOW_MS:
            bpm_avg = beats_total * (60000 // WINDOW_MS)  # factor 3
            valor_text = str(bpm_avg)
            display.clear()
            state = SHOW_LOOP
            continue

        sleep(DT_MS)

    # ---- VALOR + CORAZÓN EN LOOP ----
    elif state == SHOW_LOOP:
        if button_b.was_pressed():          # nueva medición
            state = COUNTDOWN
            continue
        # Mostrar número
        display.scroll(valor_text, delay=120, wait=True)
        # Corazón palpitante
        display.show(Image.HEART);  sleep(250)
        display.show(Image.HEART_SMALL); sleep(250)
