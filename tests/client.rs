//! The client against a local listener: no request leaves the machine.
#![cfg(feature = "client")]

use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;

use ng_postcode::api::{self, ApiError};
use ng_postcode::client::{Client, Error};

#[test]
fn a_redirect_is_not_followed() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let served = Arc::new(AtomicUsize::new(0));
    let (count, location) = (Arc::clone(&served), format!("{base}/elsewhere"));
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut lines = BufReader::new(stream.try_clone().unwrap()).lines();
            while lines.next().is_some_and(|line| !line.unwrap().is_empty()) {}
            count.fetch_add(1, Ordering::SeqCst);
            let reply = format!(
                "HTTP/1.1 302 Found\r\nLocation: {location}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            );
            stream.write_all(reply.as_bytes()).unwrap();
        }
    });

    let code = "FC-03-B06-AG-12".parse().unwrap();
    let result = Client::new("secret")
        .with_base_url(base)
        .send(&api::lookup(code, 1).unwrap());

    assert!(matches!(
        result,
        Err(Error::Api(ApiError::Malformed { status: 302, .. }))
    ));
    assert_eq!(served.load(Ordering::SeqCst), 1);
}
