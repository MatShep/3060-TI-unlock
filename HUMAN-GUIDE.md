# Human Guide

This is an experimental, machine-specific UEFI procedure, not a generic GPU
upgrade. No VBIOS flashing is involved. Begin with an agent's read-only review.

## 1. Give Your Agent This Prompt

> Help me evaluate the RTX 3060 Ti UEFI tensor unlock. Read the linked source
> repositories and this guide. First identify my exact GPU/subsystem, VBIOS,
> PCI location, motherboard, display routing, Windows driver and boot security.
> Do not flash anything, change settings, format a drive or run the unlock yet.
> Explain compatibility, missing evidence and recovery steps. Back up an
> explicitly identified spare USB before proposing changes. Preserve every
> safety check. Prepare and validate a card-specific build only when supported.
> Collect a locked baseline, supervise one manual attempt, verify its log, then
> run the same benchmark. Do not upload private files or publish without approval.

The agent should follow [the agent guide](AGENT-GUIDE.md), not treat a matching
GPU model name as proof that someone else's EFI will work.

## 2. Prepare The PC And USB

1. Save your work and arrange a recovery path. If disk encryption is enabled,
   retain recovery keys before any firmware-security change.
2. Keep a monitor on the motherboard/iGPU, connected and powered on before
   boot. The GPU being reset cannot also provide the only recovery console.
3. Insert a spare USB. Have the agent verify its identity, back up its files,
   and validate its FAT32 package. Formatting requires separate approval.
4. Review any necessary UEFI/Secure Boot changes before making them. The
   unsigned test image must be permitted to start; do not clear security keys.
5. Run the locked baseline with GPU applications closed. Keep the same monitor
   arrangement, driver, limits and tuning for the unlocked comparison.

## 3. Boot And Attempt Once

These keys refer to the tested local v0.16 build; other builds may differ.

1. Shut down fully. Once off, switch the PSU off for 30 seconds, then on.
2. Open the motherboard's one-time boot menu. On the tested MSI board, tap
   **F11**, then select the **UEFI USB** entry, not a legacy/CSM entry.
3. Check that the prepared build and its compatibility checks are correct.
   Press **U once**, only when its explicit confirmation prompt appears.
4. On success, let it start Windows automatically. Do not restart or power off
   between the unlock and Windows: this is a volatile, boot-session change.
5. If it reports STOP/POWER OFF, or makes no progress for two minutes after U,
   photograph the screen and power off physically. Do not reset or retry in
   that boot. Keep the USB connected until off; request a log review first.

An early refusal is not a successful unlock. A missing iGPU display must be
fixed physically, not by deleting the display guard.

## 4. Verify And Measure

Ask the agent to archive the new `GPU-UNLOCK/RUNxx/REPORT.TXT`, verify the
firmware result and cleanup, and run three Windows benchmark trials. Firmware
success, Windows startup and measured throughput are three separate checks.

Use [the benchmark instructions](BENCHMARK.md). Ordinary card specifications
and unchanged VBIOS are not a tensor-throughput test. Do not claim an identical
speedup in every AI application. Recheck the state after a restart or power loss.
