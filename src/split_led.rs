//! Split connection status LED (nice!nano user LED, P0_15, active-high).
//!
//! - Linked (peripheral <-> central): LED off
//! - Peer missing: LED blinks (~1.25 Hz) — a powered half that is not
//!   connected to its peer is immediately visible.
//! - Linked but this half's battery <= LOW_BATTERY_PERCENT: brief flash every
//!   2 s (distinct from the peer-missing blink). Peer-missing takes priority.

use embedded_hal::digital::StatefulOutputPin;
use rmk::event::{CentralConnectedEvent, PeripheralConnectedEvent};
use rmk::input_device::battery::current_battery_status;
use rmk::macros::processor;
use rmk::types::battery::BatteryStatus;

/// Below or at this level the LED flashes briefly every 2 s while linked.
const LOW_BATTERY_PERCENT: u8 = 20;
/// Poll period in ms (see `poll_interval` below); all patterns are in ticks of this.
const TICK_MS: u64 = 100;
/// Peer-missing blink toggles every 4 ticks (400 ms -> ~1.25 Hz).
const MISSING_HALF_PERIOD_TICKS: u8 = 4;
/// Low-battery flash: on for 1 tick every 20 ticks (2 s).
const LOW_BATTERY_PERIOD_TICKS: u8 = 20;

#[processor(
    subscribe = [CentralConnectedEvent, PeripheralConnectedEvent],
    poll_interval = 100
)]
pub struct SplitStatusLed<P: StatefulOutputPin> {
    led: P,
    /// `true` when running on the central half
    central_side: bool,
    /// Peripheral's link to the central (published by the peripheral)
    central_connected: bool,
    /// Central's link to the peripheral (published by the central)
    peripheral_connected: bool,
    tick: u8,
}

impl<P: StatefulOutputPin> SplitStatusLed<P> {
    pub fn new(led: P, central_side: bool) -> Self {
        Self {
            led,
            central_side,
            central_connected: false,
            peripheral_connected: false,
            tick: 0,
        }
    }

    fn linked(&self) -> bool {
        if self.central_side {
            self.peripheral_connected
        } else {
            self.central_connected
        }
    }

    async fn on_central_connected_event(&mut self, event: CentralConnectedEvent) {
        self.central_connected = event.connected;
    }

    async fn on_peripheral_connected_event(&mut self, event: PeripheralConnectedEvent) {
        self.peripheral_connected = event.connected;
    }

    fn battery_low(&self) -> bool {
        matches!(
            current_battery_status(),
            BatteryStatus::Available { level: Some(l), .. } if l <= LOW_BATTERY_PERCENT
        )
    }

    async fn poll(&mut self) {
        let _ = TICK_MS;
        self.tick = (self.tick + 1) % (MISSING_HALF_PERIOD_TICKS * 2 * LOW_BATTERY_PERIOD_TICKS);
        let on = if !self.linked() {
            (self.tick / MISSING_HALF_PERIOD_TICKS) % 2 == 1
        } else if self.battery_low() {
            self.tick % LOW_BATTERY_PERIOD_TICKS == 0
        } else {
            false
        };
        if on {
            self.led.set_high().ok();
        } else {
            self.led.set_low().ok();
        }
    }
}
