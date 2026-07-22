# Firmware / embedded methodology

Loaded for `embedded` / `firmware` project class — bare-metal C/C++, Zephyr, FreeRTOS, ESP-IDF, STM32Cube, Yocto, and similar.

## Secure boot

- **Root-of-trust**: ROM code verifies first-stage bootloader. Is the ROM key well-protected? Is there a fallback to unsigned boot for development that ships in production?
- **Chain of trust**: each stage verifies the next. Any stage that doesn't verify → break.
- **Signature algorithm**: ECDSA P-256/P-384 or RSA-3072+; no SHA-1, no MD5.
- **Anti-rollback**: monotonic counter (eFuse / OTP / TPM NV). Block downgrade to vulnerable versions.
- **Debug-mode lock**: production-signed firmware must not accept debug boot paths.

## Debug interfaces

- **JTAG / SWD**: disabled in production, or fused-off. If accessible, attacker with physical access reads RAM and flash.
- **UART console**: authentication required; no default credentials; no drop-to-shell on boot errors.
- **USB DFU / fastboot**: requires signed images; locked mode with unlock needing key.
- **Network debug**: telnet, rsh, bootp probes — off in production.
- **Development backdoors**: grep for `#ifdef DEBUG`, backdoor credentials, hardcoded master keys.

## OTA updates

- Images signed with offline key; firmware verifies before applying.
- Full-image signature, not just header.
- Metadata (version, target-device) also signed.
- Certificate pinning for update-server TLS.
- Resume-from-interrupt safe (A/B partitions, fallback on first-boot failure).
- Delta updates: verify reconstructed image signature, not just delta signature.
- Anti-rollback as above.

## Storage

- **Keys** in secure element / TEE / secure enclave / eFuse, not in general flash.
- **Secrets at rest**: encrypted flash (ESP32 flash encryption, iMX HAB, etc.).
- **Wear levelling does not protect secrets** — encrypt.
- **RAM wipe** on boot for secret regions (don't trust prior content).

## Memory safety

C/C++ code dominates firmware. Expect:
- Stack overflows from `strcpy`, `sprintf`, `gets`, `strcat` on attacker-controlled inputs.
- Integer overflow before `malloc` → small buffer, large copy.
- Unchecked length in protocol parsers (BLE, LoRa, Modbus, CAN, proprietary).
- Format-string bugs: `printf(user_controlled)`.
- UAF on interrupt + main-thread shared data.

Mitigations to check:
- Stack canaries (`-fstack-protector-strong`).
- ASLR (limited on MCUs), NX (XN bit on ARM).
- MPU/MMU regions for privileged vs unprivileged tasks.
- Bounded-by-construction libs (e.g., `mbedtls` configured with input caps).

Static tools: Coverity, PVS-Studio, `scan-build`, `cppcheck --enable=all`. Runtime: ASan / UBSan on host-target test builds.

## Protocols

- BLE: pairing mode (Just Works is unauthenticated MITM-able; prefer LE Secure Connections with OOB or passkey), GATT service ACLs.
- Wi-Fi: WPA2-PSK minimum; WPA3 where possible. AP mode with default passwords — never ship.
- TLS: minimum 1.2, prefer 1.3. Proper cert validation. No leaf-pinning without rotation plan.
- MQTT: TLS + client cert or strong password; topic ACLs.
- CoAP / DTLS: use DTLS 1.2+ with PSK or certs; replay window.
- Zigbee / Thread / Matter: use stack-provided pairing; provisioning code distribution matters.

## Hardware attacks (document, mitigate within reason)

- Glitching (voltage, clock, EM) to skip secure-boot checks.
- Side-channels (timing, power): constant-time crypto for key operations.
- Fault-injection hardening: redundant checks on critical branches (e.g., `if (verify() && verify())`).
- Chip-level flash readback: dependent on MCU — some have readout protection.

## Compliance / ecosystem

- CE / FCC / FTC cybersecurity requirements where applicable (depending on target market).
- Follow CVD (coordinated vulnerability disclosure) processes.
- Provide a VEX / SBOM for firmware components.
- Keep a documented support lifecycle (after X date, no more patches).

## Tool recipe

- `binwalk` — firmware image decomposition.
- `ghidra` / `ida` / `radare2` — reverse engineering.
- `checksec.sh` — mitigations present on ELF.
- `semgrep` with C/C++ ruleset.
- `clang-tidy` with security checkers.
- `afl++` / `honggfuzz` for native fuzzing of parsers.
- `Rehersal` / `chipsec` — firmware platform security.
