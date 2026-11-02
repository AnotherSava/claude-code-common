# qBittorrent bound to a VPN interface: stuck disconnected, and the rebind

qBittorrent can be bound to one network interface (Options → Advanced → Network interface, the
`current_network_interface` preference) so that it never leaks traffic outside a VPN tunnel. That
binding has a failure mode that looks like a dead swarm rather than a network problem.

## The symptom

If qBittorrent opens its listening sockets before the VPN's adapter exists, it stays unconnected even
after the adapter comes up. Measured 2026-11-02 on Windows with qBittorrent 5.1.0 and a WireGuard-based
VPN client, the two launched about 200 ms apart:

- `GET /api/v2/transfer/info` → `connection_status: "disconnected"`, `dht_nodes: 0`
- the tunnel adapter reports `Up` (`Get-NetAdapter`)
- the status bar shows a red globe and `DHT: 0 nodes`
- torrents sit in `stalledDL` with `num_seeds: 0`, so anything that shows only the seed count reads it as
  "no seeders" while a healthy swarm exists

It does not fix itself: hours later it was still in that state. A VPN that reconnects and recreates its
adapter while qBittorrent runs can, presumably, leave it the same way.

## The fix: a new listen port

Anything that changes the listen port makes qBittorrent reopen its sockets on the bound interface. In the
GUI that is the "Random" button next to the port. Through the WebUI API it is `app/setPreferences`, and
moving the port away and back leaves the setting where it was. An unauthenticated call gets `403` unless
the localhost bypass is on, so log in first and carry the `SID` cookie it sets. When that bypass applies,
and why the Web UI's default address also listens on the VPN adapter, is in
[qbittorrent-webui-api.md](qbittorrent-webui-api.md) under "Turning the Web UI on for local scripts only".

```bash
Q=http://127.0.0.1:8080/api/v2
curl -s -c qb.cookies --data-urlencode 'username={{webui-user}}' --data-urlencode 'password={{webui-password}}' $Q/auth/login
curl -s -b qb.cookies --data-urlencode 'json={"listen_port":{{listen-port-plus-one}}}' $Q/app/setPreferences
sleep 3
curl -s -b qb.cookies --data-urlencode 'json={"listen_port":{{listen-port}}}' $Q/app/setPreferences
```

With the localhost bypass on, the login call and the cookie flags can be dropped.

Measured: `disconnected`/0 nodes before; `connected` with ~245 DHT nodes 10 s after; data flowing within
a minute; `current_network_interface` unchanged. The away-and-back was measured with a 3 s gap between
the two calls; a back-to-back pair was not measured.

Do not "fix" it by clearing `current_network_interface` and setting it again: for the interval in between
qBittorrent is bound to every interface, which is exactly the leak the binding exists to stop.

## Telling it apart

- `connection_status` is one of `connected`, `firewalled`, `disconnected`. Behind a VPN without port
  forwarding `firewalled` is normal and outgoing connections still work; only `disconnected` means no
  listening socket at all.
- `dht_nodes: 0` together with `disconnected` is this case, or the tunnel genuinely down. Check the
  adapter to tell the two apart; the port move fixes only the first, and is harmless in the second.
- Both fields come in `sync/maindata`'s `server_state` too, sent only when they change.

Prevention is starting qBittorrent only after the adapter is up; a periodic check that moves the port when
`disconnected` persists for about a minute covers that and a mid-session VPN reconnect as well.
