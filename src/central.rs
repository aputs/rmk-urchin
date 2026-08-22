#![no_main]
#![no_std]

mod split_led;

use rmk::macros::rmk_central;

#[rmk_central]
mod keyboard_central {
    #[register_processor(poll)]
    fn split_status_led() -> crate::split_led::SplitStatusLed<::embassy_nrf::gpio::Output<'static>>
    {
        crate::split_led::SplitStatusLed::new(
            ::embassy_nrf::gpio::Output::new(
                p.P0_15,
                ::embassy_nrf::gpio::Level::Low,
                ::embassy_nrf::gpio::OutputDrive::Standard,
            ),
            true,
        )
    }
}
