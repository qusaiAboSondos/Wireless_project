"""
Component 2: Controlled Interference Signal Generator
Transmits a configurable interference signal within the 2.4 GHz ISM band
using ADALM-PLUTO SDR and logs receiver performance metrics (ping / throughput).

SAFETY: Operate indoors only, directed at equipment owned by the group,
for 30–60 seconds per configuration. Comply with ISM band regulations.
"""

import numpy as np
import adi
import time
import subprocess
import threading
import csv
import os
from datetime import datetime


PLUTO_IP   = "ip:192.168.2.1"
SAMPLE_RATE = 20e6   # 20 MHz

# Default interference parameters (2.4 GHz ISM)
DEFAULT_CF        = 2437e6   # Wi-Fi channel 6 centre (Hz)
DEFAULT_BW_MHZ    = 20       # Interference bandwidth (MHz)
DEFAULT_TX_GAIN   = -10      # dBm (keep low for indoor use)
DEFAULT_DURATION  = 30       # seconds


# ─── Signal generators ────────────────────────────────────────────────────────

def generate_wideband_noise(num_samples: int, bandwidth_hz: float) -> np.ndarray:
    """Bandlimited Gaussian noise centred at 0 Hz (will be upconverted by LO)."""
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)
    # FIR low-pass to restrict to desired bandwidth
    taps  = 64
    cutoff = bandwidth_hz / SAMPLE_RATE          # normalised 0–1
    w     = np.sinc(2 * cutoff * (np.arange(taps) - taps / 2))
    w    *= np.blackman(taps)
    w    /= w.sum()
    noise_filtered = np.convolve(noise.real, w, mode="same").astype(np.float32) + \
                     1j * np.convolve(noise.imag, w, mode="same").astype(np.float32)
    # Normalise to unit amplitude
    noise_filtered /= (np.max(np.abs(noise_filtered)) + 1e-12)
    return noise_filtered.astype(np.complex64)


def generate_cw_tone(num_samples: int, offset_hz: float = 0.0) -> np.ndarray:
    """Single continuous-wave tone (unmodulated carrier + optional offset)."""
    t    = np.arange(num_samples) / SAMPLE_RATE
    sig  = np.exp(1j * 2 * np.pi * offset_hz * t).astype(np.complex64)
    return sig


def generate_swept_tone(num_samples: int, bw_hz: float) -> np.ndarray:
    """Linear frequency sweep across ±bw/2 (chirp signal)."""
    t    = np.arange(num_samples) / SAMPLE_RATE
    sig  = np.exp(1j * np.pi * (bw_hz / (t[-1] + 1e-12)) * t ** 2).astype(np.complex64)
    return sig


# ─── Metrics collection ───────────────────────────────────────────────────────

def measure_ping(target_ip: str, count: int = 5) -> dict:
    """Run ping and return min/avg/max RTT and packet loss."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "2", target_ip],
            capture_output=True, text=True, timeout=20
        )
        output = result.stdout
        # Parse packet loss
        loss   = 100.0
        for line in output.splitlines():
            if "packet loss" in line:
                loss = float(line.split("%")[0].split()[-1])
        # Parse RTT stats
        rtt_min = rtt_avg = rtt_max = float("nan")
        for line in output.splitlines():
            if "rtt min" in line or "round-trip" in line:
                parts    = line.split("=")[-1].strip().split("/")
                rtt_min, rtt_avg, rtt_max = float(parts[0]), float(parts[1]), float(parts[2].split()[0])
        return {"loss_pct": loss, "rtt_min_ms": rtt_min,
                "rtt_avg_ms": rtt_avg, "rtt_max_ms": rtt_max}
    except Exception as e:
        return {"loss_pct": float("nan"), "rtt_min_ms": float("nan"),
                "rtt_avg_ms": float("nan"), "rtt_max_ms": float("nan"), "error": str(e)}


def continuous_ping_log(target_ip: str, stop_event: threading.Event,
                        results: list, interval_s: float = 2.0) -> None:
    """Background thread: ping every interval_s and append results."""
    while not stop_event.is_set():
        ts  = datetime.now().strftime("%H:%M:%S")
        m   = measure_ping(target_ip, count=3)
        m["timestamp"] = ts
        results.append(m)
        print(f"  [PING {ts}]  loss={m['loss_pct']:.0f}%  "
              f"rtt_avg={m['rtt_avg_ms']:.1f} ms")
        time.sleep(interval_s)


# ─── Transmitter ──────────────────────────────────────────────────────────────

def transmit_interference(center_freq_hz: float, bandwidth_hz: float,
                           tx_gain_db: int, duration_s: float,
                           signal_type: str = "noise",
                           uri: str | None = None) -> None:
    """Configure PlutoSDR TX and transmit interference for duration_s seconds."""
    sdr = adi.Pluto(uri or PLUTO_IP)
    sdr.sample_rate         = int(SAMPLE_RATE)
    sdr.tx_rf_bandwidth     = int(SAMPLE_RATE)
    sdr.tx_lo               = int(center_freq_hz)
    sdr.tx_hardwaregain_chan0 = tx_gain_db
    sdr.tx_cyclic_buffer    = True

    num_samples = 2 ** 15   # buffer size

    if signal_type == "noise":
        iq = generate_wideband_noise(num_samples, bandwidth_hz)
    elif signal_type == "cw":
        iq = generate_cw_tone(num_samples)
    elif signal_type == "sweep":
        iq = generate_swept_tone(num_samples, bandwidth_hz)
    else:
        raise ValueError(f"Unknown signal type: {signal_type}")

    # Scale to int16 range
    scale = 2 ** 14
    sdr.tx(iq * scale)

    print(f"[TX] Transmitting {signal_type} interference:")
    print(f"     Centre: {center_freq_hz/1e6:.3f} MHz")
    print(f"     BW:     {bandwidth_hz/1e6:.1f} MHz")
    print(f"     Gain:   {tx_gain_db} dB")
    print(f"     Duration: {duration_s} s")

    time.sleep(duration_s)
    sdr.tx_destroy_buffer()
    del sdr
    print("[TX] Transmission stopped.")


# ─── Experiment runner ────────────────────────────────────────────────────────

def run_experiment(config: dict) -> dict:
    """
    Run a single interference experiment:
      - Start continuous ping logging in background
      - Transmit interference for config['duration_s']
      - Stop logging and return results
    """
    target_ip  = config.get("target_ip", "8.8.8.8")
    duration_s = config.get("duration_s", DEFAULT_DURATION)

    # Baseline ping (no interference)
    print("\n[BASELINE] Measuring baseline network performance (no interference) …")
    baseline = measure_ping(target_ip, count=10)
    print(f"  Baseline → loss={baseline['loss_pct']:.0f}%  "
          f"rtt_avg={baseline['rtt_avg_ms']:.1f} ms")

    # Start background ping monitor
    stop_event = threading.Event()
    ping_results: list = []
    ping_thread = threading.Thread(
        target=continuous_ping_log,
        args=(target_ip, stop_event, ping_results, 2.0),
        daemon=True
    )
    ping_thread.start()

    # Transmit interference
    time.sleep(1)   # let ping thread start
    transmit_interference(
        center_freq_hz=config.get("center_freq_hz", DEFAULT_CF),
        bandwidth_hz=config.get("bandwidth_hz", DEFAULT_BW_MHZ * 1e6),
        tx_gain_db=config.get("tx_gain_db", DEFAULT_TX_GAIN),
        duration_s=duration_s,
        signal_type=config.get("signal_type", "noise"),
        uri=config.get("pluto_uri", None),
    )

    # Stop ping logging
    stop_event.set()
    ping_thread.join(timeout=5)

    # Summarise results
    if ping_results:
        avg_loss = np.nanmean([r["loss_pct"]   for r in ping_results])
        avg_rtt  = np.nanmean([r["rtt_avg_ms"] for r in ping_results])
    else:
        avg_loss = avg_rtt = float("nan")

    summary = {
        "config":       config,
        "baseline":     baseline,
        "during_interference": {"loss_pct": avg_loss, "rtt_avg_ms": avg_rtt},
        "raw_pings":    ping_results,
    }
    return summary


def save_results(results: list, filename: str | None = None) -> str:
    if filename is None:
        filename = f"interference_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="") as f:
        fieldnames = ["experiment", "center_freq_mhz", "bandwidth_mhz",
                      "signal_type", "tx_gain_db", "duration_s",
                      "baseline_loss_pct", "baseline_rtt_ms",
                      "interference_loss_pct", "interference_rtt_ms"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(results, 1):
            cfg = r["config"]
            writer.writerow({
                "experiment":            i,
                "center_freq_mhz":       cfg.get("center_freq_hz", DEFAULT_CF) / 1e6,
                "bandwidth_mhz":         cfg.get("bandwidth_hz",   DEFAULT_BW_MHZ * 1e6) / 1e6,
                "signal_type":           cfg.get("signal_type",    "noise"),
                "tx_gain_db":            cfg.get("tx_gain_db",     DEFAULT_TX_GAIN),
                "duration_s":            cfg.get("duration_s",     DEFAULT_DURATION),
                "baseline_loss_pct":     r["baseline"]["loss_pct"],
                "baseline_rtt_ms":       r["baseline"]["rtt_avg_ms"],
                "interference_loss_pct": r["during_interference"]["loss_pct"],
                "interference_rtt_ms":   r["during_interference"]["rtt_avg_ms"],
            })
    print(f"[INFO] Results saved to {filename}")
    return filename


def print_summary(results: list) -> None:
    print("\n" + "═" * 60)
    print("  EXPERIMENT SUMMARY")
    print("═" * 60)
    print(f"{'#':<4} {'BW (MHz)':<10} {'Type':<8} {'Base Loss':<12} "
          f"{'Int Loss':<12} {'Base RTT':<12} {'Int RTT':<12}")
    print("─" * 60)
    for i, r in enumerate(results, 1):
        cfg = r["config"]
        bw  = cfg.get("bandwidth_hz", DEFAULT_BW_MHZ * 1e6) / 1e6
        st  = cfg.get("signal_type", "noise")
        bl  = r["baseline"]["loss_pct"]
        il  = r["during_interference"]["loss_pct"]
        br  = r["baseline"]["rtt_avg_ms"]
        ir  = r["during_interference"]["rtt_avg_ms"]
        print(f"{i:<4} {bw:<10.1f} {st:<8} {bl:<12.1f} {il:<12.1f} {br:<12.1f} {ir:<12.1f}")
    print("═" * 60)


def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║  ENCS5323 – Interference Generator       ║")
    print("╚══════════════════════════════════════════╝")
    print("\nWARNING: Transmit only toward equipment you own, indoors.")

    target_ip = input("\nTarget IP to ping (e.g. 192.168.1.1 or 8.8.8.8): ").strip() or "8.8.8.8"

    # ── Experiment configurations ──────────────────────────────────────────────
    # Example: full Wi-Fi channel 6 (20 MHz) vs half (10 MHz) bandwidth
    experiments = [
        {
            "name":          "Full Ch6 BW (20 MHz noise)",
            "center_freq_hz": 2437e6,
            "bandwidth_hz":   20e6,
            "signal_type":    "noise",
            "tx_gain_db":     DEFAULT_TX_GAIN,
            "duration_s":     30,
            "target_ip":      target_ip,
        },
        {
            "name":          "Half Ch6 BW (10 MHz noise)",
            "center_freq_hz": 2437e6,
            "bandwidth_hz":   10e6,
            "signal_type":    "noise",
            "tx_gain_db":     DEFAULT_TX_GAIN,
            "duration_s":     30,
            "target_ip":      target_ip,
        },
        {
            "name":          "CW tone at Ch6 centre",
            "center_freq_hz": 2437e6,
            "bandwidth_hz":   1e6,
            "signal_type":    "cw",
            "tx_gain_db":     DEFAULT_TX_GAIN,
            "duration_s":     30,
            "target_ip":      target_ip,
        },
    ]

    print(f"\nPlanned experiments ({len(experiments)}):")
    for i, exp in enumerate(experiments, 1):
        print(f"  {i}. {exp['name']}")

    run_all = input("\nRun all experiments? [y/n]: ").strip().lower()
    if run_all == "n":
        idx = int(input(f"Select experiment [1–{len(experiments)}]: ")) - 1
        experiments = [experiments[idx]]

    all_results = []
    for exp in experiments:
        print(f"\n{'─'*50}")
        print(f"[EXP] {exp['name']}")
        result = run_experiment(exp)
        all_results.append(result)
        print(f"[EXP] Done. Waiting 10 s before next experiment …")
        time.sleep(10)

    print_summary(all_results)
    save_results(all_results)


if __name__ == "__main__":
    main()
