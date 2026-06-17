"""
ENCS5323 – Main Entry Point
Runs Component 1 (spectrum sensing) and Component 2 (interference generator)
independently or concurrently, supporting two separate ADALM-PLUTO devices.
"""

import threading
import time
import argparse
import sys

import spectrum_sensing       as sensing
import interference_generator as interference


# ─── Helpers ──────────────────────────────────────────────────────────────────

def ask_uris() -> tuple[str, str]:
    """
    Ask the user for the URIs of the two PLUTO devices.
    Common formats:
      ip:192.168.2.1    ← default IP (first device plugged in)
      ip:192.168.2.2    ← second device if you changed its IP
      usb:X.Y.Z         ← USB address shown by `iio_info --scan`
    """
    print("\nRun `iio_info --scan` if you are unsure of the device URIs.")
    rx_uri = input("  RX device URI (sensing)      [ip:192.168.2.1]: ").strip() or "ip:192.168.2.1"
    tx_uri = input("  TX device URI (interference) [ip:192.168.2.2]: ").strip() or "ip:192.168.2.2"
    return rx_uri, tx_uri


# ─── Modes ────────────────────────────────────────────────────────────────────

def run_sensing_only(rx_uri: str | None = None) -> None:
    if rx_uri is None:
        rx_uri = input(f"\nRX device URI [{sensing.PLUTO_IP}]: ").strip() or sensing.PLUTO_IP
    sensing.PLUTO_IP = rx_uri
    sensing.main()


def run_interference_only(tx_uri: str | None = None) -> None:
    if tx_uri is None:
        tx_uri = input(f"\nTX device URI [{interference.PLUTO_IP}]: ").strip() or interference.PLUTO_IP
    interference.PLUTO_IP = tx_uri
    interference.main()


def run_concurrent(rx_uri: str | None = None, tx_uri: str | None = None) -> None:
    """
    Parallel mode:
      - PLUTO #2 (TX) transmits interference in a background thread
      - PLUTO #1 (RX) simultaneously senses and displays the spectrum live
    """
    print("╔══════════════════════════════════════════════════╗")
    print("║  ENCS5323 – Concurrent Mode                      ║")
    print("║  PLUTO #1 → RX (sensing)                         ║")
    print("║  PLUTO #2 → TX (interference)                    ║")
    print("╚══════════════════════════════════════════════════╝\n")

    if rx_uri is None or tx_uri is None:
        rx_uri, tx_uri = ask_uris()

    # ── Interference configuration ──────────────────────────────────────────
    target_ip = input("Target IP to ping during interference [8.8.8.8]: ").strip() or "8.8.8.8"
    tx_config = {
        "name":           "Concurrent interference",
        "center_freq_hz": 2437e6,
        "bandwidth_hz":   20e6,
        "signal_type":    "noise",
        "tx_gain_db":     -10,
        "duration_s":     60,
        "target_ip":      target_ip,
        "pluto_uri":      tx_uri,         # TX device
    }

    # ── Sensing configuration ────────────────────────────────────────────────
    sense_cf    = 2437e6
    sense_label = "2.4 GHz ISM – Live (concurrent with TX)"
    sense_dur   = 60.0

    print(f"\n[INFO] RX device: {rx_uri}")
    print(f"[INFO] TX device: {tx_uri}")
    print("[INFO] Starting interference transmitter thread …")

    results_store: list = []

    def tx_thread_fn():
        interference.PLUTO_IP = tx_uri
        r = interference.run_experiment(tx_config)
        results_store.append(r)

    tx_thread = threading.Thread(target=tx_thread_fn, daemon=True)
    tx_thread.start()
    time.sleep(2)   # let TX start before sensing

    print("[INFO] Starting live spectrum sensing (close the window to stop) …")
    sensing.live_spectrum(sense_cf, sense_label, duration_s=sense_dur, uri=rx_uri)

    tx_thread.join(timeout=tx_config["duration_s"] + 10)

    if results_store:
        interference.print_summary(results_store)
        interference.save_results(results_store)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ENCS5323 SDR Project – Spectrum Sensing & Interference Analysis"
    )
    parser.add_argument(
        "--mode", choices=["sense", "interfere", "concurrent", "menu"],
        default="menu",
        help="Operating mode (default: interactive menu)"
    )
    parser.add_argument("--rx-uri", default=None, help="URI for RX (sensing) device")
    parser.add_argument("--tx-uri", default=None, help="URI for TX (interference) device")
    args = parser.parse_args()

    # Allow URIs to be passed via CLI flags (useful for scripting)
    if args.rx_uri:
        sensing.PLUTO_IP = args.rx_uri
    if args.tx_uri:
        interference.PLUTO_IP = args.tx_uri

    if args.mode == "sense":
        run_sensing_only(rx_uri=args.rx_uri)
    elif args.mode == "interfere":
        run_interference_only(tx_uri=args.tx_uri)
    elif args.mode == "concurrent":
        run_concurrent(rx_uri=args.rx_uri, tx_uri=args.tx_uri)
    else:
        print("╔══════════════════════════════════════════╗")
        print("║  ENCS5323 – SDR Project Main Menu        ║")
        print("╚══════════════════════════════════════════╝")
        print("\n  1. Spectrum Sensing only       (Component 1 – PLUTO #1)")
        print("  2. Interference Generator only  (Component 2 – PLUTO #2)")
        print("  3. Concurrent mode              (Both PLUTOs together)")
        print("  4. Exit")
        choice = input("\nSelect [1–4]: ").strip()
        if choice == "1":
            run_sensing_only()
        elif choice == "2":
            run_interference_only()
        elif choice == "3":
            run_concurrent()
        elif choice == "4":
            sys.exit(0)
        else:
            print("Invalid choice.")
            sys.exit(1)


if __name__ == "__main__":
    main()
