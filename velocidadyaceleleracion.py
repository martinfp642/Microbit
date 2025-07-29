# micro:bit v2 – Logger Acc/Vel + modelo v(t)=vmax(1−e^{-t/τ})
from microbit import *
import math, music, radio, utime

# ---------- PARÁMETROS ----------
SAMPLE_HZ   = 100
HPF_TAU     = 400          # ms para filtro IIR
RADIO_GROUP = 1
BEEP_FREQ   = 880
DURATIONS   = [5, 10, 20, 30, 40]         # s
DECIMATE    = 10          # guarda 1 de cada 10 muestras para el ajuste
# ---------------------------------

radio.config(group=RADIO_GROUP, power=7)

# ---------- FUNCIONES ----------
def auto_calibrate(n=100):
    sx = sy = sz = 0
    for _ in range(n):
        x, y, z = accelerometer.get_values()
        sx += x; sy += y; sz += z
        sleep(int(1000/SAMPLE_HZ))
    ox, oy, oz = sx/n, sy/n, sz/n
    gx, gy, gz = ox*0.00980665, oy*0.00980665, oz*0.00980665
    return ox, oy, oz, gx, gy, gz

def countdown(sec=8):
    for s in range(sec,0,-1):
        display.show(str(s%10))
        music.pitch(BEEP_FREQ,200)
        sleep(800)

def progress_led(elapsed,total):
    frac = elapsed/float(total)
    leds = int(25*frac+0.5)
    img = Image(5,5)
    for k in range(leds):
        img.set_pixel(k%5,k//5,9)
    display.show(img)

def fit_exponential(vel_samples):
    """Ajusta v(t)=vmax(1-exp(-t/tau)). Devuelve (vmax,tau)."""
    vmax = max(v for t,v in vel_samples) or 0.001
    sum_t2 = 0.0
    sum_t_ln = 0.0
    for t,v in vel_samples:
        if v>=vmax:          # evita log(0)
            continue
        r = 1.0 - v / vmax
        if r<=0:
            continue
        ln_r = math.log(r)
        sum_t2 += t*t
        sum_t_ln += t*ln_r
    if sum_t2 == 0:
        return vmax, 0.0
    slope = sum_t_ln / sum_t2   # ≈ -1/τ
    tau = -1.0/slope if slope!=0 else 0.0
    return vmax, tau

# ---------- BUCLE PRINCIPAL ----------
while True:
    # ===== MENÚ =====
    idx = 0
    display.scroll('SEL')
    display.show(str(DURATIONS[idx]))
    while True:
        if button_a.was_pressed():
            idx = (idx+1)%len(DURATIONS)  # adelante
            display.show(str(DURATIONS[idx]))
        if button_b.was_pressed():
            idx = (idx-1)%len(DURATIONS)  # atrás
            display.show(str(DURATIONS[idx]))
        if button_a.is_pressed() and button_b.is_pressed():  # A+B = OK
            run_sec = DURATIONS[idx]
            while button_a.is_pressed() or button_b.is_pressed():
                sleep(10)
            break
        sleep(50)

    # ===== CALIBRACIÓN Y CUENTA ATRÁS =====
    display.show(Image.HAPPY)
    off_x,off_y,off_z,gf_x,gf_y,gf_z = auto_calibrate()
    countdown(8)

    # ===== MEDICIÓN =====
    total_ms = run_sec*1000
    start_ms = utime.ticks_ms()
    last_ms  = start_ms
    prev_ax = prev_ay = prev_az = 0.0
    have_prev = False
    vx=vy=vz=0.0
    sum_a=sum_v=0.0
    samples=0
    vel_samples=[]   # para el ajuste
    while True:
        now_ms = utime.ticks_ms()
        elapsed = utime.ticks_diff(now_ms,start_ms)
        if elapsed >= total_ms:
            break
        dt_ms = utime.ticks_diff(now_ms,last_ms)
        last_ms = now_ms
        dt = dt_ms/1000.0
        if dt<=0:
            continue

        # Lectura y escala
        rx,ry,rz = accelerometer.get_values()
        ax = (rx-off_x)*0.00980665
        ay = (ry-off_y)*0.00980665
        az = (rz-off_z)*0.00980665

        # Filtro IIR de gravedad
        alpha = HPF_TAU/float(HPF_TAU+dt_ms)
        gf_x = alpha*gf_x + (1-alpha)*ax
        gf_y = alpha*gf_y + (1-alpha)*ay
        gf_z = alpha*gf_z + (1-alpha)*az
        ax_d = ax - gf_x
        ay_d = ay - gf_y
        az_d = az - gf_z

        # Aceleración mag.
        a_mag = math.sqrt(ax_d*ax_d + ay_d*ay_d + az_d*az_d)
        sum_a += a_mag

        # Integración trapezoidal para velocidad
        if have_prev:
            vx += (prev_ax+ax_d)*dt/2.0
            vy += (prev_ay+ay_d)*dt/2.0
            vz += (prev_az+az_d)*dt/2.0
        else:
            have_prev = True
        prev_ax,prev_ay,prev_az = ax_d,ay_d,az_d

        v_mag = math.sqrt(vx*vx + vy*vy + vz*vz)
        sum_v += v_mag
        if samples%DECIMATE==0:
            vel_samples.append((elapsed/1000.0, v_mag))

        samples += 1
        progress_led(elapsed,total_ms)
        sleep(max(0,int(1000/SAMPLE_HZ)-1))

    mean_a = sum_a/samples
    mean_v = sum_v/samples
    vmax,tau = fit_exponential(vel_samples)

    # ===== ENVÍO Y LOOP DE RESULTADOS =====
    radio.send("a:{:.3f},v:{:.3f},vm:{:.3f},t:{:.3f}".format(
               mean_a,mean_v,vmax,tau))

    while True:
        display.scroll("A {:.2f}".format(mean_a),wait=False,delay=80)
        sleep(400)
        display.scroll("V {:.2f}".format(mean_v),wait=False,delay=80)
        sleep(400)
        display.scroll("VM {:.2f}".format(vmax),wait=False,delay=80)
        sleep(400)
        display.scroll("T {:.2f}".format(tau),wait=False,delay=80)
        sleep(400)
        if button_b.was_pressed():        # volver al menú
            display.clear()
            break
