//! One-shot flash-wipe firmware for the rmk-urchin nRF52840 halves.
//!
//! Erases the TOP portion of flash (0x50000..0x100000), which contains the
//! SDC (BLE controller) bond/keys region and the application storage
//! partition, then drops into the Adafruit UF2 bootloader.
//!
//! Safety:
//!   - The app code lives at 0x1100..~0x4A904 (peripheral) / ~0x75000 (central).
//!     We start erasing at 0x50000, well above the running code, so the CPU
//!     never fetches from an erased sector.
//!   - The Adafruit bootloader occupies the first 4KB (0x0..0x1000) and is
//!     never touched.
//!   - After the erase we set POWER.GPRET=0x57 and reset, so the bootloader
//!     presents the UF2 drive for a normal reflash.
//!
//! Build:  cargo build --release --bin wipe
//! Flash:  drag the resulting wipe.uf2 onto the target half's UF2 drive.

#![no_main]
#![no_std]

// Pull in the nRF52840 device crate so cortex-m-rt generates the interrupt vectors.
use nrf_pac::Interrupt;

const FLASH_START: u32 = 0x0005_0000;
const FLASH_END: u32 = 0x0010_0000;
const SECTOR: u32 = 0x1000; // nRF52840 4KB sectors

// NVMC register addresses (base 0x4006_E000)
const NVMC_UNLOCK: u32 = 0x4006_E304;
const NVMC_ERASE: u32 = 0x4006_E310;
const NVMC_READY: u32 = 0x4006_E31C;

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    loop {}
}

#[no_mangle]
pub extern "C" fn Default() {
    loop {}
}

#[cortex_m_rt::entry]
fn main() -> ! {
    unsafe {
        // Unlock the flash controller for erase/program.
        core::ptr::write_volatile(NVMC_UNLOCK as *mut u32, 0xC0DD_C0DD);

        // Erase every 4KB sector in [FLASH_START, FLASH_END).
        let mut addr = FLASH_START;
        while addr < FLASH_END {
            core::ptr::write_volatile(NVMC_ERASE as *mut u32, addr);
            // Wait for ERASEREADY (READY bit 1).
            while core::ptr::read_volatile(NVMC_READY as *const u32) & (1 << 1) == 0 {}
            addr += SECTOR;
        }
    }

    // Tell the Adafruit nRF52 bootloader to enter UF2 mode on reset.
    // POWER.GPREGRET = 0x4007_4000 + 0x514
    unsafe { core::ptr::write_volatile(0x4007_4514 as *mut u32, 0x57) };
    cortex_m::peripheral::SCB::sys_reset();

    unreachable!()
}
