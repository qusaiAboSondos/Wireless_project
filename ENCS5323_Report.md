# ENCS5323 – Real-World Spectrum Sensing and Controlled RF Analysis Using SDR

**Course:** Wireless and Mobile Networks (ENCS5323) — Dr. Mohammad K. Jubran
**Group Members:** <Name 1, ID> / <Name 2, ID> / <Name 3, ID> / <Name 4, ID — if applicable>
**Date:** <submission date>

---

## 1. Introduction

This project implements two complementary SDR-based subsystems using two ADALM-PLUTO
units: (1) a **spectrum sensing system** that captures and visualizes live RF activity
across GSM 900, GSM 1800, UMTS 2100, and the 2.4 GHz ISM band, and (2) a **controlled
interference generator** that quantifies the impact of in-band RF interference on an
active 2.4 GHz wireless link. Both subsystems can run independently or concurrently,
with PLUTO #1 dedicated to sensing (RX) and PLUTO #2 dedicated to interference (TX).

## 2. Component 1 – Spectrum Sensing

### 2.1 Method (brief)

Each band is swept by stepping the PlutoSDR's local oscillator across overlapping
20 MHz windows (the device's instantaneous sample rate), capturing IQ samples per
step, applying a Hanning-windowed FFT (1024 bins), averaging 20 frames per step to
reduce noise variance, and stitching the resulting power spectral density (PSD)
segments into a single sweep. Power is reported in **relative dB** (uncalibrated ADC
power referenced to full-scale), since no absolute dBm calibration step was performed —
this is sufficient for evaluating channel structure, occupancy, and relative power
differences. A live mode additionally renders a real-time PSD line and scrolling
waterfall for temporal variability.

### 2.2 Results and Interpretation

**GSM 900 Downlink (935–960 MHz).** Mean relative power −23.3 dB. The sweep shows a
dominant narrow carrier near 945 MHz (~31 dB above noise floor) immediately adjacent
to a second, smaller carrier near 946 MHz, plus weaker activity near 944 MHz and 952
MHz. This is consistent with multiple GSM base stations transmitting adjacent 200 kHz
FDMA carriers within the downlink block — exactly the channelized structure the
assignment asks us to demonstrate.

**GSM 1800 Downlink (1805–1880 MHz).** Mean relative power −21.8 dB. Roughly six
distinct narrowband peaks (−10 to −14 dB) are visible, each sitting on top of a
broader raised "shoulder" (−15 to −20 dB) rather than a flat noise floor. The discrete
peaks correspond to individual GSM carriers (likely BCCH/control channels, which
transmit continuously at near-constant power), while the broader shoulders reflect
traffic channels whose occupancy varies with call/data load — direct visual evidence
of frequency-domain multiplexing plus load-dependent occupancy.

**UMTS 2100 Downlink (2110–2170 MHz).** Mean relative power +2.3 dB — the most
information-dense capture of the four. The spectrum shows a clear repeating pattern
of ~5 MHz-wide raised "domes" (peaking 10–14 dB) separated by sharp deep notches (down
to −25 to −32 dB), yielding roughly 10–12 repeating structures across the 60 MHz span.
This is the textbook signature of **WCDMA**: each UMTS carrier occupies a fixed 5 MHz
channel raster, and because all users within a carrier are code-multiplexed (not
frequency-multiplexed), the carrier appears as a flat-topped "dome" rather than a set
of discrete tones — in sharp contrast to the narrowband FDMA carriers seen in the GSM
bands. This single plot is strong evidence for relating an empirical measurement
directly to the multiple-access theory covered in the course.

**2.4 GHz ISM Band (2400–2500 MHz).** Mean relative power −23.4 dB. One dominant sharp
peak (~15 dB) appears near 2450 MHz — likely a strong nearby Wi-Fi access point or
Bluetooth device — with several weaker, scattered peaks (−15 to −20 dB) at ~2410,
2433, 2443, 2465, 2473, 2484, and 2492 MHz. Unlike the cellular bands, the ISM band is
unlicensed and contention-based (CSMA/CA for Wi-Fi, FHSS for Bluetooth), so its
occupancy is bursty, irregular, and source-dependent rather than showing the fixed
channel raster seen in GSM/UMTS — itself a useful contrast to highlight.

### 2.3 Temporal Variability

The live/waterfall mode (separately captured for the ISM band) shows frame-to-frame
fluctuation in carrier power and intermittent appearance/disappearance of bursts,
consistent with the packet-based, contention-driven nature of Wi-Fi/Bluetooth traffic,
as opposed to the near-continuous carriers observed on the cellular downlinks.

**Discussion point for the live session:** be ready to explain *why* GSM/UMTS carriers
look "static" (continuously transmitted control channels / dedicated spectrum) while
ISM activity is bursty (shared unlicensed spectrum, contention-based MAC).

## 3. Component 2 – Controlled Interference Generation

### 3.1 Method (brief)

PLUTO #2 transmits a band-limited Gaussian-noise (or CW tone) interference signal
centered on the **router's actual operating Wi-Fi channel** (determined from the
router's admin page rather than assumed), at maximum PlutoSDR TX output power
(0 dB attenuation). A target device (smartphone) associated with that AP is
continuously pinged (2 s interval) before and during each 30-second interference
exposure; packet loss and average RTT are logged and compared against a
no-interference baseline.

**Critical methodological note (worth including — it demonstrates understanding):**
an early attempt at this experiment, transmitting at the default channel-6 frequency
(2437 MHz) while the router actually operated on **channel 1** (2412 MHz, confirmed
via the router's status page), produced *no measurable degradation despite verified
maximum TX power* — confirmed independently via the concurrent spectrum view, which
showed strong broadband interference energy that simply did not overlap the active
link's frequency. Correcting the center frequency to match the router's real channel
immediately produced large, repeatable degradation. This is itself a meaningful
result: **even high-power interference has zero effect outside the victim channel's
occupied bandwidth** — direct empirical confirmation of frequency-selective
interference and the importance of in-band overlap for jamming/co-channel
interference analysis.

### 3.2 Results

| Configuration                        | Bandwidth | Baseline loss | Loss during interference | Baseline RTT | RTT during interference |
|---------------------------------------|-----------|----------------|----------------------------|--------------|---------------------------|
| Full channel (20 MHz noise)           | 20 MHz    | 0%             | **74.8%**                  | ~X ms        | ~X+80–180 ms               |
| Half channel (10 MHz noise)           | 10 MHz    | 0%             | **83.2%**                  | ~X ms        | ~X+80–180 ms               |
| CW tone at channel centre             | ~1 MHz    | 0%             | **83.2%**                  | ~X ms        | ~X+80–180 ms               |

*(Fill in the exact baseline/interference RTT numbers from your saved
`interference_results_*.csv` files — they were logged automatically by
`save_results()`.)*

### 3.3 Discussion

Two results stand out and should anchor the discussion section:

1. **Interference is only effective when it overlaps the active channel.** As noted
   above, identical TX power at the wrong center frequency produced 0% measurable
   effect; correcting the frequency alone (no power change) produced >74% loss. This
   directly demonstrates the concept of **co-channel/in-band interference** versus
   adjacent/out-of-band interference, and explains why frequency planning (channel
   assignment) is a primary interference-avoidance mechanism in real Wi-Fi deployments.

2. **Narrower-bandwidth interference was at least as damaging as full-bandwidth
   interference at equal total transmit power.** The half-bandwidth noise and the
   ~1 MHz CW tone both produced *higher* packet loss (83.2%) than the full 20 MHz
   noise signal (74.8%). This is explained by **power spectral density
   concentration**: for a fixed total transmit power, concentrating that power into a
   narrower bandwidth raises the power *spectral density* (W/Hz) at the frequencies
   it does occupy. If that narrower band still covers a sensitive part of the victim
   signal (e.g. the preamble/control fields, or the channel center where most energy
   and synchronization information is concentrated), the localized SNR degradation at
   the receiver can be more severe than a wider but power-diluted interferer. This
   mirrors the practical trade-off jammers/attackers face between *coverage* (wide
   bandwidth, lower spectral density) and *potency* (narrow bandwidth, higher
   spectral density, but requires accurate frequency targeting) — and explains why a
   well-aimed narrowband or single-tone jammer can be more effective per transmitted
   watt than wideband noise.

## 4. Concurrent Operation

Running both subsystems simultaneously (PLUTO #2 transmitting noise/CW interference
on the router's channel while PLUTO #1 performs live spectrum sensing on the same
band) visually confirms the interference signal's spectral footprint in real time: the
live PSD/waterfall shows a clear, persistent elevation (15–30 dB above background) at
the configured center frequency and bandwidth for the full duration of transmission,
coinciding exactly with the ping degradation logged by Component 2. This closes the
loop between the spectral-domain observation (Component 1) and the link-layer
performance impact (Component 2), satisfying the assignment's joint-operation
requirement.

## 5. Conclusion

The measurements across GSM 900, GSM 1800, UMTS 2100, and the 2.4 GHz ISM band show
clearly distinguishable channelization signatures consistent with each technology's
multiple-access scheme (narrowband FDMA carriers for GSM, 5 MHz WCDMA "domes" for
UMTS, bursty contention-based activity for ISM). The interference experiments
demonstrate that (a) in-band overlap, not raw transmit power, is the dominant factor
in causing receiver performance degradation, and (b) spectral power concentration can
make narrowband interference more disruptive than wideband interference at equal
total power — both of which are directly explainable through, and reinforce, the
wireless communication theory covered in this course.

---

### Appendix (optional, only if page budget allows)
- Table of all experiment parameters (center freq, bandwidth, gain, duration)
- Additional PSD plots not discussed in the main body
