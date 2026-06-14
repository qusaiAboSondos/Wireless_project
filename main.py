"""
ENCS5323 – Main Entry Point
Runs Component 1 (spectrum sensing) and Component 2 (interference generator)
independently or concurrently.
"""

import threading
import time
import argparse
import sys

import spectrum_sensing     as sensing
import interference_generator as interference


def run_sensing_only() -> None:
    sensing.main()


def run_interference_only() -> None:
    interference.main()


def run_concurrent() -> None:
    """
    Parallel mode:
      - Component 2 transmits interference in a background thread
      - Component 1 simultaneously senses and displays the spectrum live
    """
    print("╔══════════════════════════════════════════════════╗")
    print("║  ENCS5323 – Concurrent Mode                      ║")
    print("║  Interference TX  +  Live Spectrum Sensing       ║")
    print("╚══════════════════════════════════════════════════╝\n")

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
    }

    # ── Sensing configuration ────────────────────────────────────────────────
    sense_cf    = 2437e6        # centre of Wi-Fi Ch 6
    sense_label = "2.4 GHz ISM – Live (concurrent with TX)"
    sense_dur   = 60.0

    print("\n[INFO] Starting interference transmitter thread …")
    results_store: list = []

    def tx_thread_fn():
        r = interference.run_experiment(tx_config)
        results_store.append(r)

    tx_thread = threading.Thread(target=tx_thread_fn, daemon=True)
    tx_thread.start()
    time.sleep(2)   # small delay so TX is active before sensing starts

    print("[INFO] Starting live spectrum sensing (close the window to stop) …")
    sensing.live_spectrum(sense_cf, sense_label, duration_s=sense_dur)

    tx_thread.join(timeout=tx_config["duration_s"] + 10)

    if results_store:
        interference.print_summary(results_store)
        interference.save_results(results_store)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ENCS5323 SDR Project – Spectrum Sensing & Interference Analysis"
    )
    parser.add_argument(
        "--mode", choices=["sense", "interfere", "concurrent", "menu"],
        default="menu",
        help="Operating mode (default: interactive menu)"
    )
    args = parser.parse_args()

    if args.mode == "sense":
        run_sensing_only()
    elif args.mode == "interfere":
        run_interference_only()
    elif args.mode == "concurrent":
        run_concurrent()
    else:
        print("╔══════════════════════════════════════════╗")
        print("║  ENCS5323 – SDR Project Main Menu        ║")
        print("╚══════════════════════════════════════════╝")
        print("\n  1. Spectrum Sensing only     (Component 1)")
        print("  2. Interference Generator only (Component 2)")
        print("  3. Concurrent mode           (Both together)")
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
