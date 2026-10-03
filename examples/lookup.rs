//! NG_POSTCODE_API_KEY=... cargo run --features client --example lookup -- FC-03-B06-AG-12

use ng_postcode::{api, client::Client, Postcode};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let key = std::env::var("NG_POSTCODE_API_KEY")?;
    let code: Postcode = std::env::args()
        .nth(1)
        .ok_or("usage: lookup <postcode>")?
        .parse()?;
    let found = Client::new(key).send(&api::lookup(code, 1)?)?;
    println!("{found:#?}");
    Ok(())
}
