"""
Component 1: Spectrum Sensing System
Uses ADALM-PLUTO SDR to capture and display live RF signals across
selected frequency bands (GSM 900, GSM 1800, UMTS 2100, 2.4 GHz ISM).
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import adi
import time
from datetime import datetime


# ─── Predefined frequency bands ───────────────────────────────────────────────
BANDS = {
    "GSM 900 Downlink":  {"start": 935e6,  "end": 960e6,  "label": "GSM 900 DL (935–960 MHz)"},
    "GSM 1800 Downlink": {"start": 1805e6, "end": 1880e6, "label": "GSM 1800 DL (1805–1880 MHz)"},
    "UMTS 2100 Downlink":{"start": 2110e6, "end": 2170e6, "label": "UMTS 2100 DL (2110–2170 MHz)"},
    "2.4 GHz ISM":       {"start": 2400e6, "end": 2500e6, "label": "2.4 GHz ISM (2400–2500 MHz)"},
    "Wi-Fi Ch 1-6":      {"start": 2412e6, "end": 2437e6, "label": "Wi-Fi Ch 1–6 (2412–2437 MHz)"},
}

# ─── SDR parameters ───────────────────────────────────────────────────────────
SAMPLE_RATE   = 20e6       # 20 MHz sample rate
RX_GAIN       = 40         # dB (manual gain)
FFT_SIZE      = 1024
NUM_FRAMES    = 20         # frames averaged per sweep step
PLUTO_IP      = "ip:192.168.2.1"   # RX device — override via --rx-uri


def create_sdr(center_freq: float, uri: str = PLUTO_IP) -> adi.Pluto:
    sdr = adi.Pluto(uri)
    sdr.sample_rate         = int(SAMPLE_RATE)
    sdr.rx_rf_bandwidth     = int(SAMPLE_RATE)
    sdr.rx_lo               = int(center_freq)
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0   = RX_GAIN
    sdr.rx_buffer_size      = FFT_SIZE * NUM_FRAMES
    return sdr


def capture_psd(sdr: adi.Pluto, center_freq: float) -> tuple[np.ndarray, np.ndarray]:
    """Capture samples and compute averaged PSD in dBm."""
    sdr.rx_lo = int(center_freq)
    time.sleep(0.05)   # settle after tuning

    samples = sdr.rx()
    # Split into frames and average
    frames = np.array_split(samples, NUM_FRAMES)
    psd_avg = np.zeros(FFT_SIZE)
    for frame in frames:
        win    = np.hanning(len(frame))
        spec   = np.fft.fftshift(np.abs(np.fft.fft(frame * win, n=FFT_SIZE)) ** 2)
        psd_avg += spec / NUM_FRAMES

    # Convert to dBm (50-ohm reference, account for window power loss)
    psd_dbm = 10 * np.log10(psd_avg / (FFT_SIZE ** 2) + 1e-20) + 30

    freqs = center_freq + np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, 1 / SAMPLE_RATE))
    return freqs, psd_dbm


def sweep_band(start_hz: float, end_hz: float,
               uri: str = PLUTO_IP) -> tuple[np.ndarray, np.ndarray]:
    """Sweep across a wide band by stepping the LO center frequency."""
    span      = end_hz - start_hz
    step      = SAMPLE_RATE * 0.8          # 80 % of bandwidth per step (avoid roll-off edges)
    centers   = np.arange(start_hz + SAMPLE_RATE / 2,
                           end_hz   + SAMPLE_RATE / 2,
                           step)

    all_freqs = np.array([])
    all_psd   = np.array([])

    sdr = create_sdr(centers[0], uri=uri)
    try:
        for cf in centers:
            f, p   = capture_psd(sdr, cf)
            # Keep only frequencies within [start_hz, end_hz]
            mask   = (f >= start_hz) & (f <= end_hz)
            all_freqs = np.concatenate([all_freqs, f[mask]])
            all_psd   = np.concatenate([all_psd,   p[mask]])
    finally:
        del sdr

    # Sort by frequency
    idx       = np.argsort(all_freqs)
    return all_freqs[idx], all_psd[idx]


def plot_psd(freqs: np.ndarray, psd: np.ndarray, band_label: str,
             save: bool = True) -> None:
    """Plot and optionally save the power spectral density."""
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(freqs / 1e6, psd, color="royalblue", linewidth=0.8)
    ax.fill_between(freqs / 1e6, psd, psd.min() - 5, alpha=0.25, color="royalblue")

    ax.set_title(f"Power Spectral Density – {band_label}\n"
                 f"Captured: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 fontsize=12)
    ax.set_xlabel("Frequency (MHz)", fontsize=11)
    ax.set_ylabel("Power (dBm)", fontsize=11)
    ax.set_xlim(freqs[0] / 1e6, freqs[-1] / 1e6)
    ax.set_ylim(psd.min() - 5, psd.max() + 5)
    ax.axhline(y=psd.mean(), color="orange", linestyle="--",
               linewidth=0.8, label=f"Mean: {psd.mean():.1f} dBm")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    plt.tight_layout()
    if save:
        fname = f"psd_{band_label.replace(' ', '_').replace('–','-')}.png"
        plt.savefig(fname, dpi=150)
        print(f"[INFO] Saved plot: {fname}")
    plt.show()


def live_spectrum(center_freq: float, band_label: str,
                  duration_s: float = 30.0, uri: str = PLUTO_IP) -> None:
    """Display a real-time scrolling spectrogram for a fixed center frequency."""
    sdr = create_sdr(center_freq, uri=uri)
    freqs = center_freq + np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, 1 / SAMPLE_RATE))

    waterfall_rows = 100
    waterfall_data = np.full((waterfall_rows, FFT_SIZE), -100.0)

    fig, (ax_psd, ax_fall) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f"Live Spectrum – {band_label}", fontsize=12)

    line,   = ax_psd.plot(freqs / 1e6, np.zeros(FFT_SIZE), color="royalblue", lw=0.8)
    ax_psd.set_xlabel("Frequency (MHz)")
    ax_psd.set_ylabel("Power (dBm)")
    ax_psd.set_xlim(freqs[0] / 1e6, freqs[-1] / 1e6)
    ax_psd.set_ylim(-100, 0)
    ax_psd.grid(True, alpha=0.3)

    img = ax_fall.imshow(waterfall_data, aspect="auto", origin="upper",
                         extent=[freqs[0] / 1e6, freqs[-1] / 1e6, waterfall_rows, 0],
                         vmin=-100, vmax=0, cmap="inferno")
    ax_fall.set_xlabel("Frequency (MHz)")
    ax_fall.set_ylabel("Time (frames, newest at top)")
    fig.colorbar(img, ax=ax_fall, label="Power (dBm)")

    start_time = time.time()

    def update(_frame):
        if time.time() - start_time > duration_s:
            ani.event_source.stop()
            del sdr
            return line, img

        raw  = sdr.rx()
        win  = np.hanning(FFT_SIZE)
        spec = np.fft.fftshift(np.abs(np.fft.fft(raw[:FFT_SIZE] * win)) ** 2)
        psd  = 10 * np.log10(spec / FFT_SIZE ** 2 + 1e-20) + 30

        line.set_ydata(psd)
        ax_psd.set_ylim(psd.min() - 5, psd.max() + 5)

        waterfall_data[1:] = waterfall_data[:-1]
        waterfall_data[0]  = psd
        img.set_data(waterfall_data)
        return line, img

    ani = animation.FuncAnimation(fig, update, interval=50, blit=False)
    plt.tight_layout()
    plt.show()


def select_band() -> tuple[float, float, str]:
    print("\n=== Spectrum Sensing – Band Selection ===")
    keys = list(BANDS.keys())
    for i, k in enumerate(keys, 1):
        b = BANDS[k]
        print(f"  {i}. {k}  ({b['start']/1e6:.0f} – {b['end']/1e6:.0f} MHz)")
    print(f"  {len(keys)+1}. Custom range")

    choice = int(input("\nSelect band [1–{}]: ".format(len(keys) + 1)))
    if 1 <= choice <= len(keys):
        band = BANDS[keys[choice - 1]]
        return band["start"], band["end"], band["label"]
    else:
        start = float(input("Start frequency (MHz): ")) * 1e6
        end   = float(input("End frequency   (MHz): ")) * 1e6
        return start, end, f"Custom ({start/1e6:.0f}–{end/1e6:.0f} MHz)"


def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║   ENCS5323 – Spectrum Sensing System     ║")
    print("╚══════════════════════════════════════════╝")

    mode = input("\nMode:\n  1. Single sweep + PSD plot\n  2. Live real-time display\nSelect [1/2]: ").strip()

    start_hz, end_hz, label = select_band()

    if mode == "2":
        cf = (start_hz + end_hz) / 2
        dur = float(input("Live display duration (seconds) [default 30]: ") or 30)
        live_spectrum(cf, label, dur)
    else:
        print(f"\n[INFO] Sweeping {label} …")
        freqs, psd = sweep_band(start_hz, end_hz)
        print(f"[INFO] Peak power: {psd.max():.1f} dBm at {freqs[np.argmax(psd)]/1e6:.3f} MHz")
        plot_psd(freqs, psd, label, save=True)


if __name__ == "__main__":
    main()
