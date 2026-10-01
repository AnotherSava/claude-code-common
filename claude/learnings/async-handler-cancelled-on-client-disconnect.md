# An async HTTP handler stops at its next await when the client hangs up

Adding an `.await` to a handler whose effects must happen makes those effects optional. Under axum 0.8 on hyper 1, a client that closes its socket mid-request makes the server drop the in-flight handler future, and a dropped future stops at whichever `.await` it was parked on. Nothing is logged, nothing after that point runs, and whatever ran before it is not rolled back.

A handler with no `.await` after its extractors cannot be cut short this way. Once polled, it runs to the end in one go. So the hazard appears exactly when someone adds the first await, typically a lock, and the handler looked safe until then.

## The mechanism

`axum::serve` builds its HTTP/1 connection with `half_close` left at its default of `false`. While a request is in flight, hyper keeps reading the socket. On EOF it fails the connection, and the connection future owns the service future, so the handler is dropped with it. With `half_close(true)`, hyper would wait for the response instead.

The usual trigger is a client-side timeout. A Python hook doing `urllib.request.urlopen(..., timeout=2)` closes the socket when the 2s elapse, so any handler still waiting past that point is gone.

## The fix

Move the work that must finish into a spawned task and await its handle. A spawned task runs to completion whether or not anyone is still awaiting it. Use `spawn_blocking` when the body is synchronous or takes a blocking lock, and plain `spawn` when it is async. Dropping a `JoinHandle` detaches the task; it does not cancel it.

```rust
async fn post_event(State(app): State<AppHandle>, Json(req): Json<EventRequest>) -> Response {
    match tauri::async_runtime::spawn_blocking(move || apply_event(&app, req)).await {
        Ok(response) => response,
        Err(e) => { tracing::error!(error = %e, "handler failed"); StatusCode::INTERNAL_SERVER_ERROR.into_response() }
    }
}
```

This also makes a blocking `std::sync::Mutex` usable inside the body, without parking an async worker thread while it waits.

## How it was found

A per-row `tokio::sync::Mutex` was added to serialize hook events, held with `lock_owned().await`. An adversarial review traced the await through hyper's `mid_message_detect_eof` and the hook's 2s timeout to a silently lost `SessionStart`, which is precisely the event the lock existed to protect. Tests could not have caught it: unit tests never drop the future, and a live probe only hits the window when the lock holder stalls for longer than the client timeout.
