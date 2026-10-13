//! CH32V006 option-byte provisioning through one uninterrupted SWIO session.
//! Sequence follows WCH FLASH_EraseOptionBytes / FLASH_OptionBytePR in the
//! repository's firmware/source/CH32V00X_IAP/User/main.c. Hardware validation pending.
use anyhow::{Context, Result, bail, ensure};
use std::{env, fs, thread, time::{Duration, Instant}};
use wlink::{RiscvChip, commands, operations::ProbeSession, probe::WchLink};

const BASE: u32 = 0x40022000;
const KEY: u32 = BASE + 4;
const OBKEY: u32 = BASE + 8;
const STATUS: u32 = BASE + 12;
const CONTROL: u32 = BASE + 16;
const ADDRESS: u32 = BASE + 20;
const MODEKEY: u32 = BASE + 36;
const OPTIONS: u32 = 0x1ffff800;
const KEY1: u32 = 0x45670123;
const KEY2: u32 = 0xcdef89ab;
const LOCK: u32 = 0x80;
const FLOCK: u32 = 0x8000;
const OPTER: u32 = 0x20;
const START: u32 = 0x40;
const PAGE_PG: u32 = 0x10000;
const BUF_LOAD: u32 = 0x40000;
const BUF_RESET: u32 = 0x80000;

fn desired_options(original: &[u8]) -> Result<Vec<u8>> {
    ensure!(original.len() == 16, "Expected a 16-byte options backup");
    ensure!((0..16).step_by(2).all(|i| original[i] ^ original[i+1] == 0xff), "Invalid complements");
    ensure!(original[0] == 0xa5, "Read-protected device: refusing to unlock");
    ensure!((8..16).step_by(2).all(|i| original[i] == 0xff), "Write-protected device: refusing to unlock");
    let mut desired = original.to_vec();
    desired[2] |= 0x20;
    desired[3] = !desired[2];
    Ok(desired)
}

fn idle(session: &mut ProbeSession) -> Result<()> {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        let status = session.read_mem32(STATUS)?;
        ensure!(status & 0x10 == 0, "Flash write-protection error");
        if status & 1 == 0 { return Ok(()); }
        ensure!(Instant::now() < deadline, "Flash controller busy timeout");
        thread::sleep(Duration::from_millis(2));
    }
}

fn modify(session: &mut ProbeSession, clear: u32, set: u32) -> Result<()> {
    let control = session.read_mem32(CONTROL)?;
    session.write_mem32(CONTROL, (control & !clear) | set)?;
    Ok(())
}

fn unlock(session: &mut ProbeSession, register: u32) -> Result<()> {
    session.write_mem32(register, KEY1)?;
    session.write_mem32(register, KEY2)?;
    Ok(())
}

fn provision(session: &mut ProbeSession, original: &[u8], desired: &[u8]) -> Result<()> {
    session.ensure_mcu_halt()?;
    // Read again with the core halted, immediately before any option-byte writes.
    ensure!(session.read_memory(OPTIONS, 16)? == original, "Options changed; refusing to erase");
    if original == desired { return Ok(()); }
    idle(session)?;
    unlock(session, KEY)?;
    unlock(session, OBKEY)?;
    // Erase only the option-byte page; never the application or BOOT pages.
    modify(session, OPTER | 0x20000, 0)?;
    modify(session, 0, OPTER)?;
    modify(session, 0, START)?;
    idle(session)?;
    modify(session, OPTER, LOCK)?;
    unlock(session, KEY)?;
    unlock(session, MODEKEY)?;
    modify(session, OPTER | 0x20000, 0)?;
    modify(session, 0, PAGE_PG)?;
    modify(session, 0, BUF_RESET)?;
    idle(session)?;
    modify(session, PAGE_PG, 0)?;
    for (i, bytes) in desired.chunks_exact(4).enumerate() {
        modify(session, OPTER | 0x20000, PAGE_PG)?;
        session.write_mem32(OPTIONS + i as u32 * 4, u32::from_le_bytes(bytes.try_into().unwrap()))?;
        modify(session, 0, BUF_LOAD)?;
        idle(session)?;
        modify(session, PAGE_PG, 0)?;
    }
    modify(session, OPTER | 0x20000, PAGE_PG)?;
    session.write_mem32(ADDRESS, OPTIONS)?;
    modify(session, 0, START)?;
    idle(session)?;
    modify(session, PAGE_PG, FLOCK | LOCK)?;
    ensure!(session.read_memory(OPTIONS, 16)? == desired, "Options readback differs; retain original backup");
    Ok(())
}

fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() == 2 && args[1] == "--help" {
        println!("holt-options --expected options-original.bin --out options-readback.bin\n\
                  Prototype CH32V006F8U6 BOOT-at-power-on configuration; hardware validation pending.");
        return Ok(());
    }
    ensure!(args.len() == 5 && args[1] == "--expected" && args[3] == "--out", "Use --help");
    let original = fs::read(&args[2]).context("Read original options backup")?;
    let desired = desired_options(&original)?;
    let probe = WchLink::open_nth(0)?;
    let mut session = ProbeSession::attach(probe, Some(RiscvChip::CH32V00X), commands::Speed::High)?;
    let chip = session.probe.send_command(commands::control::AttachChip)?;
    ensure!(chip.chip_id == 0x00620620, "Expected Holt CH32V006F8U6, got {chip}");
    println!("Configuring {chip}; preserving every option field except BOOT-at-power-on");
    if let Err(error) = provision(&mut session, &original, &desired) {
        // Best-effort lock, no automatic erase/retry/restore after a failed operation.
        let _ = modify(&mut session, PAGE_PG | OPTER, FLOCK | LOCK);
        bail!("Option provisioning failed: {error:#}. Keep backups and recover using WCH tools.");
    }
    let readback = session.read_memory(OPTIONS, 16)?;
    fs::write(&args[4], &readback)?;
    println!("PASS: option bytes verified. Core remains halted; cold power-cycle required.");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn options(user: u8) -> Vec<u8> {
        vec![0xa5,0x5a,user,!user,0x12,0xed,0x34,0xcb,0xff,0,0xff,0,0xff,0,0xff,0]
    }
    #[test]
    fn preserves_every_other_field() {
        for user in 0..=255u8 {
            let original = options(user);
            let changed = desired_options(&original).unwrap();
            assert_eq!(changed[2], user | 0x20);
            assert_eq!(changed[3], !changed[2]);
            for i in (0..16).filter(|i| *i != 2 && *i != 3) { assert_eq!(original[i], changed[i]); }
        }
    }
    #[test]
    fn rejects_protection_and_corruption() {
        let mut data = options(0xd7);
        data[0] = 0; data[1] = 0xff;
        assert!(desired_options(&data).is_err());
        let mut data = options(0xd7); data[8] = 0xfe; data[9] = 1;
        assert!(desired_options(&data).is_err());
        assert!(desired_options(&[0; 16]).is_err());
    }
}
