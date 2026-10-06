//! The client against a local listener: no request leaves the machine.
#![cfg(feature = "client")]

use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

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

#[test]
fn a_body_that_stalls_times_out() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let head = "HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{\"data\":";
        stream.write_all(head.as_bytes()).unwrap();
        thread::sleep(Duration::from_secs(5));
    });

    let code = "FC-03-B06-AG-12".parse().unwrap();
    let started = Instant::now();
    let result = Client::new("secret")
        .with_base_url(base)
        .with_timeout(Duration::from_millis(300))
        .send(&api::lookup(code, 1).unwrap());

    assert!(matches!(result, Err(Error::Transport(_))));
    assert!(started.elapsed() < Duration::from_secs(2));
}
