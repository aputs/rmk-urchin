//! Split connection status LED (nice!nano user LED, P0_15, active-high).
//!
//! - Linked (peripheral <-> central): LED off
//! - Peer missing: LED blinks (~1.25 Hz) — a powered half that is not
//!   connected to its peer is immediately visible.

use embedded_hal::digital::StatefulOutputPin;
use rmk::event::{CentralConnectedEvent, PeripheralConnectedEvent};
use rmk::macros::processor;

#[processor(
    subscribe = [CentralConnectedEvent, PeripheralConnectedEvent],
    poll_interval = 400
)]
pub struct SplitStatusLed<P: StatefulOutputPin> {
    led: P,
    /// `true` when running on the central half
    central_side: bool,
    /// Peripheral's link to the central (published by the peripheral)
    central_connected: bool,
    /// Central's link to the peripheral (published by the central)
    peripheral_connected: bool,
    phase: bool,
}

impl<P: StatefulOutputPin> SplitStatusLed<P> {
    pub fn new(led: P, central_side: bool) -> Self {
        Self {
            led,
            central_side,
            central_connected: false,
            peripheral_connected: false,
            phase: false,
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

    async fn poll(&mut self) {
        if self.linked() {
            self.led.set_low().ok();
        } else {
            self.phase = !self.phase;
            if self.phase {
                self.led.set_high().ok();
            } else {
                self.led.set_low().ok();
            }
        }
    }
}
